"""Select the drugs in the atlas by rule, not by hand.

Rule: a medicine is included if
  1. the FDA approved it as a NEW active substance between 2019 and 2025
     (an original NDA classed "Type 1 - new molecular entity", or an original
     BLA, from openFDA Drugs@FDA), AND
  2. the European Commission's FIRST authorisation of the same active
     substance(s) also falls between 2019 and 2025 (EMA medicines data;
     generics and biosimilars excluded).

Cell and gene therapies are approved by FDA's CBER and are not in openFDA.
For those we start from the EMA list of advanced therapies authorised in the
window, and include each one whose FDA approval date (researched by hand, in
data/manual/us_fda.csv) also falls in the window.

Diagnostic agents (ATC V04, V09) are excluded: they are not treatments and are
reimbursed through different routes.

Biosimilars and new formulations of old molecules drop out automatically,
because their active substance was first authorised in the EU before 2019.

Output: data/manual/drugs.csv (existing drug_ids are kept), plus a review
file data/raw/universe/candidates.json showing every match.

This is a one-off selection step (the study window is closed), not part of
the monthly refresh.  Run:  python3 pipeline/universe.py
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
from datetime import datetime

from common import CACHE, MANUAL, RAW, http_get, read_csv, write_json

WINDOW = ("2019-01-01", "2025-12-31")
EMA_URL = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json"
FDA_QUERY = ("https://api.fda.gov/drug/drugsfda.json?search={q}&limit=1000&skip={skip}")

# Words that are not part of an active substance's identity (salts, forms).
NOISE = {
    "hydrochloride", "dihydrochloride", "sodium", "disodium", "potassium", "calcium", "magnesium",
    "mesylate", "mesilate", "maleate", "fumarate", "hemifumarate", "tartrate", "citrate", "succinate",
    "phosphate", "sulfate", "sulphate", "acetate", "besylate", "besilate", "tosylate", "tosilate",
    "bromide", "chloride", "monohydrate", "dihydrate", "trihydrate", "sesquihydrate", "hemihydrate",
    "hydrate", "anhydrous", "tromethamine", "meglumine", "dimeglumine", "hydrobromide", "benzoate",
    "lactate", "malate", "oxalate", "edisylate", "camsylate", "free", "base", "injection", "oral",
    "and", "fam", "trometamol",
}
# Salt names of two words, and a misspelling in the EMA file, found by the FDA cross-check
# (pipeline/crosscheck_fda.py): without these, Mayzent and Vocabria did not match.
SALT_PHRASES = ("fumaric acid",)
SPELLING = {"cabotegavir": "cabotegravir"}

# Drugs the rule selects but openFDA no longer holds: Pepaxto (melphalan flufenamide) was
# withdrawn in the US and removed from openFDA. Its FDA approval is verified by hand in
# data/manual/us_fda.csv, as for cell and gene therapies.
NOT_IN_OPENFDA = {"EMEA/H/C/005681": "Pepaxto"}
# A new substance the FDA first approved inside a co-pack with an older one, while the EU
# authorised it on its own: cabotegravir (new) came with rilpivirine (EU 2011) in Cabenuva;
# the EU authorised cabotegravir alone as Vocabria. FDA application -> EU product.
CO_PACKAGED = {"NDA212888": "EMEA/H/C/004976"}

# Rybelsus and Wegovy are new brands of an older molecule (semaglutide, first
# approved as Ozempic in 2017), so the rule excludes them. They are kept as a
# labelled reference pair because Medicare negotiated their price.
REFERENCE = {"EMEA/H/C/004953": "rybelsus", "EMEA/H/C/005422": "wegovy"}


def tokens(name: str) -> frozenset:
    """Reduce a substance name to comparable words: 'FAM-TRASTUZUMAB DERUXTECAN-NXKI' -> {trastuzumab, deruxtecan}."""
    name = name.lower()
    for phrase in SALT_PHRASES:
        name = name.replace(phrase, " ")
    for wrong, right in SPELLING.items():
        name = re.sub(rf"\b{wrong}\b", right, name)
    name = re.sub(r"-[a-z]{4}\b", "", name)   # US biologic suffixes such as -nxki
    name = re.sub(r"\(.*?\)", " ", name)       # isotope notes such as (177Lu)
    words = set(re.findall(r"[a-z][a-z0-9]+", name)) - NOISE
    return frozenset(w for w in words if len(w) > 3)


def ema_date(record) -> str:
    return datetime.strptime(record["marketing_authorisation_date"], "%d/%m/%Y").date().isoformat()


def fda_new_substances() -> dict:
    """Original approvals 2019-2025: NME NDAs and all original BLAs."""
    found = {}
    for year in range(2019, 2026):
        skip = 0
        while True:
            q = urllib.parse.quote(f"submissions.submission_type:ORIG AND submissions.submission_status:AP "
                                   f"AND submissions.submission_status_date:[{year}0101 TO {year}1231]")
            data = json.loads(http_get(FDA_QUERY.format(q=q, skip=skip)))
            for r in data["results"]:
                app = r["application_number"]
                if app.startswith("ANDA"):
                    continue
                for s in r.get("submissions", []):
                    if (s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
                            and s.get("submission_status_date", "")[:4] == str(year)):
                        cls = s.get("submission_class_code") or ""
                        if app.startswith("BLA") or cls.startswith("TYPE 1"):
                            found[app] = {
                                "application": app,
                                "approval": s["submission_status_date"],
                                "class": cls or "BLA",
                                "brands": sorted({p.get("brand_name", "") for p in r.get("products", [])}),
                                "ingredients": sorted({ai.get("name", "") for p in r.get("products", [])
                                                       for ai in p.get("active_ingredients", [])}),
                            }
            skip += 1000
            if skip >= data["meta"]["results"]["total"]:
                break
            time.sleep(0.5)
    return found


def clean_brand(brands: list[str]) -> str:
    names = sorted({re.sub(r"\s*\(.*?\)", "", b).strip() for b in brands if b}, key=len)
    return names[0].title() if names else ""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def main() -> None:
    ema_path = CACHE / "ema_medicines_full.json"
    if not ema_path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        ema_path.write_bytes(http_get(EMA_URL))
    ema = [r for r in json.loads(ema_path.read_text())["data"]
           if r.get("category") == "Human" and r.get("generic") != "Yes" and r.get("biosimilar") != "Yes"
           and r.get("marketing_authorisation_date")]
    by_tokens = {}
    for r in ema:
        key = tokens(r.get("active_substance") or r.get("international_non_proprietary_name_common_name") or "")
        if key:
            by_tokens.setdefault(key, []).append(r)

    # ---- CDER: match each FDA new substance to the EU's first authorisation of it
    print("Querying openFDA for original approvals 2019-2025 ...")
    fda = fda_new_substances()
    matches = {}
    for app, f in sorted(fda.items(), key=lambda kv: kv[1]["approval"]):
        key = frozenset().union(*[tokens(i) for i in f["ingredients"]]) if f["ingredients"] else frozenset()
        eu = by_tokens.get(key)
        if not eu:
            continue
        first = min(eu, key=ema_date)
        if not (WINDOW[0] <= ema_date(first) <= WINDOW[1]):
            continue  # substance was already authorised in the EU before 2019
        if (first.get("atc_code_human") or "").startswith(("V04", "V09")):
            continue  # diagnostic imaging and test agents: not treatments, reimbursed differently
        # One EU product can match several FDA applications (e.g. Mounjaro and Zepbound):
        # keep the earliest FDA approval.
        matches.setdefault(first["ema_product_number"], {"fda": f, "ema": first})

    ema_by_number = {r["ema_product_number"]: r for r in ema}
    for app, number in CO_PACKAGED.items():
        if app in fda and WINDOW[0] <= ema_date(ema_by_number[number]) <= WINDOW[1]:
            matches.setdefault(number, {"fda": fda[app], "ema": ema_by_number[number]})

    # ---- CBER: EU advanced therapies in the window (FDA dates are researched by hand)
    atmps = [r for r in ema if r.get("advanced_therapy") == "Yes" and WINDOW[0] <= ema_date(r) <= WINDOW[1]]

    # ---- Write drugs.csv, keeping existing ids
    existing = {r["ema_product_number"]: r for r in read_csv(MANUAL / "drugs.csv")}
    rows, used_ids = [], set()

    def add(ema_rec, fda_app, brand_us, center, cohort):
        number = ema_rec["ema_product_number"]
        old = existing.get(number)
        drug_id = old["drug_id"] if old else slug(ema_rec["name_of_medicine"].split("(")[0])
        while drug_id in used_ids:
            drug_id += "x"
        used_ids.add(drug_id)
        rows.append({
            "drug_id": drug_id,
            "brand_us": old["brand_us"] if old and old.get("brand_us") else brand_us,
            "brand_eu": re.sub(r"\s*\(previously.*?\)", "", ema_rec["name_of_medicine"]).strip(),
            "inn": (ema_rec.get("international_non_proprietary_name_common_name")
                    or ema_rec.get("active_substance") or "").strip().lower(),
            "fda_application": fda_app,
            "ema_product_number": number,
            "fda_center": center,
            "cohort": cohort,
        })

    for number, m in matches.items():
        add(m["ema"], m["fda"]["application"], clean_brand(m["fda"]["brands"]), "CDER", "core")
    # A CBER product is included only if its FDA approval date has been verified
    # (data/manual/us_fda.csv) and falls in the window.
    manual = {(m["drug_id"], m["field"]): m for m in read_csv(MANUAL / "us_fda.csv")}
    excluded = []
    for r in atmps:
        if r["ema_product_number"] in matches:
            continue
        old = existing.get(r["ema_product_number"])
        drug_id = old["drug_id"] if old else slug(r["name_of_medicine"].split("(")[0])
        date_row = manual.get((drug_id, "fda_approval_date"))
        if not date_row or date_row["status"] != "verified" or not (WINDOW[0] <= date_row["value"] <= WINDOW[1]):
            excluded.append({"eu_name": r["name_of_medicine"], "reason": "no verified FDA approval in the window"})
            continue
        brand = manual.get((drug_id, "fda_brand"), {}).get("value", "").title()
        add(r, "", brand, "CBER", "core")
    ema_by_number = {r["ema_product_number"]: r for r in ema}
    # Selected by the rule but absent from openFDA: included only with a verified FDA date in the window.
    for number, brand in NOT_IN_OPENFDA.items():
        r = ema_by_number[number]
        old = existing.get(number)
        drug_id = old["drug_id"] if old else slug(r["name_of_medicine"].split("(")[0])
        date_row = manual.get((drug_id, "fda_approval_date"))
        if date_row and date_row["status"] == "verified" and WINDOW[0] <= date_row["value"] <= WINDOW[1]:
            add(r, "", brand, "CDER", "core")
        else:
            excluded.append({"eu_name": r["name_of_medicine"], "reason": "not in openFDA; no verified FDA approval in the window"})
    for number in REFERENCE:
        add(ema_by_number[number], existing[number]["fda_application"], existing[number]["brand_us"], "CDER", "reference")

    rows.sort(key=lambda r: r["brand_eu"].lower())
    with open(MANUAL / "drugs.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    write_json(RAW / "universe" / "candidates.json", {
        "rule": __doc__.split("Output:")[0].strip(),
        "cder_matches": [{"ema_product_number": k, "eu_name": v["ema"]["name_of_medicine"],
                          "ec_first_authorisation": ema_date(v["ema"]), **v["fda"]} for k, v in matches.items()],
        "cber_candidates": [{"ema_product_number": r["ema_product_number"], "eu_name": r["name_of_medicine"],
                             "ec_first_authorisation": ema_date(r)} for r in atmps],
        "excluded": excluded,
    })
    print(f"  ok   {len(matches)} CDER drugs + {len(atmps) - len(excluded)} cell/gene therapies (+{len(REFERENCE)} reference) "
          f"-> data/manual/drugs.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
