"""Fetch French HAS benefit ratings from the public medicines database (BDPM).

Source:  Base de données publique des médicaments (ANSM / HAS / CNAM)
         https://base-donnees-publique.medicaments.gouv.fr/telechargement
Terms:   Licence ouverte: free reuse provided the data is not altered and the
         source and update date are cited.

What we take, per drug, from the HAS Transparency Committee (CT) opinions:
  - SMR (service médical rendu): is the drug worth reimbursing at all?
    important / moderate / low / insufficient
  - ASMR (amélioration du SMR): added benefit vs existing care, I (major) to V (none)
  - the date of the FIRST opinion on inclusion ("Inscription") for the brand

The drug is matched to French product records (CIS codes) by its EU brand name
among centrally authorised products. The HAS opinion page is used as the source link.
"""
from __future__ import annotations

import csv
import io
import json
import re

from common import CACHE, http_get, load_drugs, save_raw

BASE = "https://base-donnees-publique.medicaments.gouv.fr/download/file/"
FILES = ["CIS_bdpm.txt", "CIS_HAS_SMR_bdpm.txt", "CIS_HAS_ASMR_bdpm.txt", "HAS_LiensPageCT_bdpm.txt"]
SMR_EN = {"important": "important", "modéré": "moderate", "modere": "moderate", "faible": "low",
          "insuffisant": "insufficient", "non précisé": None, "commentaires": None}


def read_tab(blob: bytes) -> list[list[str]]:
    text = blob.decode("latin-1")
    return list(csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE))


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    tables = {}
    for name in FILES:
        blob = http_get(BASE + name)
        (CACHE / name).write_bytes(blob)
        tables[name] = read_tab(blob)

    # CIS records of centrally authorised products, indexed by the first word(s) of the name.
    cis_rows = [r for r in tables["CIS_bdpm.txt"] if len(r) > 5 and "centralis" in r[5].lower()]
    links = {r[0]: r[1] for r in tables["HAS_LiensPageCT_bdpm.txt"] if len(r) >= 2}

    def opinions(table, value_col):
        out = {}
        for r in tables[table]:
            if len(r) > value_col:
                out.setdefault(r[0], []).append({"dossier": r[1], "reason": r[2], "date": r[3], "value": r[4].strip()})
        return out

    smr, asmr = opinions("CIS_HAS_SMR_bdpm.txt", 4), opinions("CIS_HAS_ASMR_bdpm.txt", 4)

    result = {}
    for drug in load_drugs():
        brand = drug["brand_eu"].upper()
        pattern = re.compile(r"^" + re.escape(brand) + r"(\b|\s|,)")
        cis = sorted({r[0] for r in cis_rows if pattern.match(r[1].upper())})
        if not cis:
            result[drug["drug_id"]] = {"matched_cis": []}
            continue
        smr_ops = [o for c in cis for o in smr.get(c, [])]
        asmr_ops = [o for c in cis for o in asmr.get(c, [])]
        # First opinion on inclusion (the initial reimbursement assessment).
        firsts = sorted([o for o in smr_ops + asmr_ops if "inscription" in o["reason"].lower()], key=lambda o: o["date"])
        if not firsts:
            result[drug["drug_id"]] = {"matched_cis": cis, "first_opinion": None}
            continue
        dossier, date = firsts[0]["dossier"], firsts[0]["date"]
        # A single opinion can give different SMR/ASMR per indication: keep them all.
        smr_values = sorted({o["value"] for o in smr_ops if o["dossier"] == dossier})
        asmr_values = sorted({o["value"] for o in asmr_ops if o["dossier"] == dossier})
        result[drug["drug_id"]] = {
            "matched_cis": cis,
            "first_opinion": {"dossier": dossier, "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                              "reason": firsts[0]["reason"], "smr": smr_values, "asmr": asmr_values,
                              "url": links.get(dossier)},
        }

    content = (json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()
    retrieved = save_raw("france/has_opinions.json", content, BASE)
    matched = sum(1 for v in result.values() if v.get("first_opinion"))
    print(f"  ok   HAS first opinions found for {matched} of {len(result)} drugs (retrieved {retrieved})")


if __name__ == "__main__":
    print("Fetching France (BDPM / HAS) ...")
    main()
