"""Watch for new HAS opinions on drugs that France has no value for yet.

Most French values come automatically from the public medicines database
(fetch_france.py). Drugs not listed there were researched by hand, and many
had no HAS opinion when checked (status not_assessed). This step looks each
month for a new opinion on any drug without a French value, in two official
HAS datasets on data.gouv.fr:

  - "Evaluation des médicaments": every SMR/ASMR opinion (updated monthly)
  - "Métadonnées des publications de la HAS": every HAS publication, including
    drugs never listed in the medicines database

It never changes a value. It writes data/processed/has_watch.json with any
matches, so a person can read the opinion and update data/manual/france_has.csv.
The monthly refresh workflow opens a GitHub issue when there are matches.

Terms: HAS open data, Licence ouverte. Pass --offline to reuse cached downloads.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import unicodedata
import zipfile

from common import CACHE, PROCESSED, http_get, write_json

API = "https://www.data.gouv.fr/api/1/datasets/"
EVALUATIONS = "600a8f554d401b8270a581fb"   # Evaluation des médicaments (SMR, ASMR)
PUBLICATIONS = "61e6c823f1eae83eac2cf47b"  # Métadonnées des publications de la HAS


def plain(text: str) -> str:
    """Upper case, accents removed, so 'décitabine' matches 'DECITABINE'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()


def resource(dataset: str, pattern: str) -> tuple[str, str]:
    """URL and update date of the newest file in a data.gouv dataset whose URL matches pattern."""
    meta = json.loads(http_get(API + dataset + "/"))
    found = [r for r in meta["resources"] if re.search(pattern, r["url"])]
    if not found:
        raise RuntimeError(f"No file matching {pattern} in data.gouv dataset {dataset}")
    newest = max(found, key=lambda r: r.get("last_modified") or "")
    return newest["url"], (newest.get("last_modified") or "")[:10]


def download(name: str, url: str, offline: bool) -> bytes:
    path = CACHE / name
    if offline and path.exists():
        return path.read_bytes()
    blob = http_get(url)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return blob


def decode(blob: bytes) -> str:
    try:
        return blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        return blob.decode("latin-1")


def smr_opinions(text: str) -> list[dict]:
    """Rows of the SMR file: fields are separated by ';' and wrapped in '$'."""
    out = []
    for line in text.splitlines()[1:]:
        f = [x.strip().strip('"').strip("$").strip() for x in line.split(";")]
        if len(f) >= 6:
            out.append({"source": "HAS SMR open data", "code": f[0], "reason": f[1], "title": f[4], "date": f[5]})
    return out


def publications(blob: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8-sig")
    csv.field_size_limit(10**9)
    out = []
    for r in csv.DictReader(io.StringIO(text, newline="")):
        if r.get("class") == "AVISMedicament":
            out.append({"source": "HAS publications", "code": r.get("id", ""), "reason": "",
                        "title": r.get("title") or "", "date": (r.get("publicationDate") or "")[:10],
                        "url": r.get("pageURL") or ""})
    return out


def matches(brand: str, inn: str, records: list[dict]) -> list[dict]:
    """A record matches if its title starts with the brand, or names every part of the INN."""
    b = re.compile(r"^" + re.escape(plain(brand)) + r"\b")
    parts = [p for p in re.split(r"[^A-Z]+", plain(inn)) if len(p) >= 5]
    hits = []
    for rec in records:
        title = plain(rec["title"])
        if b.match(title) or (parts and all(re.search(r"\b" + p + r"\b", title) for p in parts)):
            hits.append(rec)
    return hits


def main(offline: bool = False) -> dict:
    drugs = json.loads((PROCESSED / "drugs.json").read_text())["drugs"]
    watched = [d for d in drugs if d["fields"]["fr_has_date"]["value"] is None]

    smr_url, smr_date = resource(EVALUATIONS, r"/smr-[^/]*\.csv$")
    pub_url, pub_date = resource(PUBLICATIONS, r"has-publications-single")
    records = (smr_opinions(decode(download("has_smr.csv", smr_url, offline)))
               + publications(download("has_publications.zip", pub_url, offline)))

    found = []
    for d in watched:
        f = d["fields"]
        hits = matches(f["brand_eu"]["value"], f["inn"]["value"] or "", records)
        if hits:
            found.append({"drug_id": d["drug_id"], "brand": f["brand_eu"]["value"],
                          "current_status": f["fr_has_date"]["status"],
                          "matches": sorted({json.dumps(h, ensure_ascii=False, sort_keys=True) for h in hits})})
    for item in found:
        item["matches"] = [json.loads(m) for m in item["matches"]]

    result = {
        "about": "Drugs with no French value for which an HAS record now exists. Review and update "
                 "data/manual/france_has.csv; this file never changes values itself.",
        # Dataset links carry a monthly timestamp, so they are printed, not stored:
        # this file changes only when what we are watching, or what we found, changes.
        "sources": ["https://www.data.gouv.fr/fr/datasets/evaluation-des-medicaments/",
                    "https://www.data.gouv.fr/fr/datasets/metadonnees-des-publications-de-la-has-1/"],
        "watched": sorted(d["drug_id"] for d in watched),
        "found": found,
    }
    write_json(PROCESSED / "has_watch.json", result)
    print(f"  ok   HAS watch: SMR file of {smr_date}, publications of {pub_date}")
    print(f"  ok   HAS watch: {len(watched)} drugs without a French value, {len(found)} with a new HAS record")
    for item in found:
        print(f"  note {item['drug_id']}: {item['matches'][0]['title'][:90]}")
    return result


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
