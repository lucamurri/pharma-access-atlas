"""Cross-check the drug selection against FDA's official "Novel Drug Approvals" lists.

The selection (pipeline/universe.py) is built from openFDA by rule. This check
compares it with FDA's own yearly lists of novel drugs (CDER new molecular
entities and new therapeutic biologics), 2019-2025, in both directions:

  1. Every drug on an FDA list should be in the atlas, unless the rule leaves it
     out for a stated reason: no EU central authorisation, an EU first
     authorisation outside 2019-2025, or a diagnostic agent.
  2. Every CDER drug in the atlas approved by FDA in one of these years should
     be on that year's list, unless there is a stated reason.

Anything not explained is printed as UNEXPLAINED for review, and the script
exits with code 1. FDA no longer hosts the 2019 and 2020 pages, so those come
from Internet Archive copies of the FDA pages taken after each year ended
(FDA's own site points to the Internet Archive for its older content).

This is a one-off check, like the selection itself. It writes
data/raw/universe/fda_crosscheck.json.

Run:  python3 pipeline/crosscheck_fda.py
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime

from common import CACHE, MANUAL, RAW, http_get, read_csv, write_json
from universe import EMA_URL, WINDOW, ema_date, tokens

FDA_LIST = "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-{year}"
ARCHIVED = {  # FDA pages no longer online; Internet Archive copies taken after the year ended
    2019: "https://web.archive.org/web/20200111010109/https://www.fda.gov/drugs/new-drugs-fda-cders-new-molecular-entities-and-new-therapeutic-biological-products/novel-drug-approvals-2019",
    2020: "https://web.archive.org/web/20210614155937/https://www.fda.gov/drugs/new-drugs-fda-cders-new-molecular-entities-and-new-therapeutic-biological-products/novel-drug-approvals-2020",
}
YEARS = range(2019, 2026)

# Differences already reviewed, with the reason. They are reported, not hidden.
KNOWN = {
    "nustendi": ("Nexlizet (bempedoic acid with ezetimibe) is coded 'Type 1/4' in openFDA, so the rule includes it; "
                 "FDA's list counts bempedoic acid once, under Nexletol (Nilemdo in the EU, also in the atlas)."),
}


def fda_list(year: int) -> tuple[str, list[dict]]:
    url = ARCHIVED.get(year) or FDA_LIST.format(year=year)
    page = http_get(url).decode("utf-8", "ignore")
    out = []
    # A few cells hold a nested table (e.g. Ebanga, 2020); flatten it to its text first.
    page = re.sub(r"<table[^>]*>\s*<tbody>\s*<tr>\s*<td[^>]*>(.*?)</td>\s*</tr>\s*</tbody>\s*</table>",
                  r"\1", page, flags=re.S)
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        # Tolerate quirks in FDA's tables ("23," for "23.", a date merged into another cell).
        if len(cells) < 3 or not re.match(r"\d{1,3}[.,]?$", cells[0]):
            continue
        found = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", " ".join(cells[3:]) or " ".join(cells))
        if not found:
            raise SystemExit(f"{year}: no approval date in row {cells[:3]}")
        m, d, y = found.groups()
        date = datetime(int(y) if len(y) == 4 else 2000 + int(y), int(m), int(d)).date().isoformat()
        out.append({"brand": cells[1], "ingredient": cells[2], "fda_date": date})
    return url, out


def main() -> int:
    ema_path = CACHE / "ema_medicines_full.json"
    if not ema_path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        ema_path.write_bytes(http_get(EMA_URL))
    ema = [r for r in json.loads(ema_path.read_text())["data"]
           if r.get("category") == "Human" and r.get("generic") != "Yes" and r.get("biosimilar") != "Yes"
           and r.get("marketing_authorisation_date")]
    ema_by_tokens = {}
    for r in ema:
        key = tokens(r.get("active_substance") or r.get("international_non_proprietary_name_common_name") or "")
        if key:
            ema_by_tokens.setdefault(key, []).append(r)

    drugs = read_csv(MANUAL / "drugs.csv")
    fda_dates = {r["drug_id"]: r["value"] for r in read_csv(MANUAL / "us_fda.csv") if r["field"] == "fda_approval_date"}
    processed = {d["drug_id"]: d["fields"] for d in json.loads((ROOT_PROCESSED).read_text())["drugs"]}
    atlas = {}
    for d in drugs:
        if d["cohort"] != "core":
            continue
        atlas[d["drug_id"]] = {**d, "key": tokens(d["inn"]),
                               "fda_date": (processed.get(d["drug_id"], {}).get("fda_approval_date") or {}).get("value")
                               or fda_dates.get(d["drug_id"])}

    def in_atlas(key: frozenset):
        if not key:
            return None
        for did, d in atlas.items():
            if d["key"] and (d["key"] == key or d["key"] <= key or key <= d["key"]):
                return did
        return None

    report, unexplained = {"years": {}}, []
    for year in YEARS:
        url, listed = fda_list(year)
        time.sleep(1)
        rows, listed_ids = [], set()
        for item in listed:
            key = tokens(item["ingredient"])
            did = in_atlas(key)
            if did:
                listed_ids.add(did)
                rows.append({**item, "status": "in atlas", "drug_id": did})
                continue
            eu = ema_by_tokens.get(key)
            # The selection matches substance names exactly (after dropping salt words), so a salt
            # word it does not know, or a misspelling in the EMA file, can hide a match. Look for
            # EU products sharing every word of the FDA substance name before calling it absent.
            # Co-packaged products (e.g. "cabotegravir and rilpivirine") are matched on their main
            # (longest) word, so a shared linker such as "vedotin" alone is not a match.
            words = {max(sorted(key), key=len)} if key else set()
            loose = [r for k, rs in ema_by_tokens.items() if key and (key <= k or words & k) for r in rs] if not eu else []
            in_window = [r for r in loose if WINDOW[0] <= ema_date(r) <= WINDOW[1]
                         and not (r.get("atc_code_human") or "").startswith(("V04", "V09"))]
            if not eu and loose and not in_window:
                first = min(loose, key=ema_date)
                reason = (f"no exact EU match; closest EU substance '{first.get('active_substance')}' "
                          f"first authorised {ema_date(first)}, outside the window")
            elif not eu and in_window and item["ingredient"].lower() not in KNOWN:
                first = min(in_window, key=ema_date)
                reason = "UNEXPLAINED"
                unexplained.append(f"{year} FDA list: {item['brand']} ({item['ingredient']}) not in atlas; possible EU "
                                   f"match {first['name_of_medicine']} ('{first.get('active_substance')}') {ema_date(first)}")
            elif not eu and item["ingredient"].lower() in KNOWN:
                reason = "known difference: " + KNOWN[item["ingredient"].lower()]
            elif not eu:
                reason = "no EU central authorisation found"
            else:
                first = min(eu, key=ema_date)
                if ema_date(first) < WINDOW[0]:
                    reason = f"EU first authorisation before the window ({ema_date(first)})"
                elif ema_date(first) > WINDOW[1]:
                    reason = f"EU first authorisation after the window ({ema_date(first)})"
                elif (first.get("atc_code_human") or "").startswith(("V04", "V09")):
                    reason = "diagnostic agent (excluded by rule)"
                elif item["ingredient"].lower() in KNOWN:
                    reason = "known difference: " + KNOWN[item["ingredient"].lower()]
                else:
                    reason = "UNEXPLAINED"
                    unexplained.append(f"{year} FDA list: {item['brand']} ({item['ingredient']}) not in atlas; "
                                       f"EU {first['name_of_medicine']} {ema_date(first)}")
            rows.append({**item, "status": "not in atlas", "reason": reason})
        # Reverse direction: atlas CDER drugs approved by FDA this year but missing from the list
        missing = []
        for did, d in atlas.items():
            if d["fda_center"] == "CDER" and (d["fda_date"] or "")[:4] == str(year) and did not in listed_ids:
                missing.append({"drug_id": did, "inn": d["inn"], "fda_date": d["fda_date"],
                                "reason": KNOWN.get(did, "UNEXPLAINED")})
                if did in KNOWN:
                    continue
                unexplained.append(f"{year} atlas: {did} ({d['inn']}, FDA {d['fda_date']}) not on FDA list")
        report["years"][str(year)] = {"source": url, "listed": len(listed),
                                      "in_atlas": sum(1 for r in rows if r["status"] == "in atlas"),
                                      "drugs": rows, "atlas_not_listed": missing}
        print(f"  {year}: {len(listed)} on FDA list, {report['years'][str(year)]['in_atlas']} in atlas, "
              f"{len(missing)} atlas CDER drugs not on the list")
    report["known_differences"] = KNOWN
    report["unexplained"] = unexplained
    write_json(RAW / "universe" / "fda_crosscheck.json", report)
    for u in unexplained:
        print("  UNEXPLAINED", u)
    return 1 if unexplained else 0


ROOT_PROCESSED = RAW.parent / "processed" / "drugs.json"

if __name__ == "__main__":
    sys.exit(main())
