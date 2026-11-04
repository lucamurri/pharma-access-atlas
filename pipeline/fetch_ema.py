"""Fetch EU approval data from the European Medicines Agency.

Source:  EMA "Download medicine data" JSON report (updated daily, free, no key)
         https://www.ema.europa.eu/en/medicines/download-medicine-data
Terms:   EMA content may be reused with acknowledgement of the source.

The full file (~7 MB, every EU-authorised medicine) is cached outside git.
We store only the records for our curated drugs in data/raw/ema/.
"""
from __future__ import annotations

import json

from common import CACHE, http_get, load_drugs, save_raw

URL = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json"

# The EMA fields we keep (names exactly as EMA publishes them).
KEEP = [
    "name_of_medicine", "ema_product_number", "medicine_status", "active_substance",
    "international_non_proprietary_name_common_name", "therapeutic_area_mesh",
    "marketing_authorisation_developer_applicant_holder", "opinion_adopted_date",
    "marketing_authorisation_date", "orphan_medicine", "conditional_approval",
    "exceptional_circumstances", "accelerated_assessment", "prime_priority_medicine",
    "advanced_therapy", "medicine_url",
]


def main() -> None:
    content = http_get(URL)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "ema_medicines_full.json").write_bytes(content)
    records = json.loads(content)["data"]
    by_number = {r["ema_product_number"]: r for r in records if r.get("category") == "Human"}

    subset = {}
    for drug in load_drugs():
        number = drug["ema_product_number"]
        record = by_number.get(number)
        if record is None:
            raise SystemExit(f"EMA product {number} ({drug['drug_id']}) not found in EMA file")
        subset[drug["drug_id"]] = {k: (record.get(k) or "").strip() for k in KEEP}

    out = (json.dumps(subset, indent=2, ensure_ascii=False) + "\n").encode()
    retrieved = save_raw("ema/medicines_subset.json", out, URL)
    print(f"  ok   {len(subset)} EMA records (retrieved {retrieved})")


if __name__ == "__main__":
    print("Fetching EMA ...")
    main()
