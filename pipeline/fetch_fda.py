"""Fetch FDA approval data from the openFDA Drugs@FDA API.

Source:  https://open.fda.gov/apis/drug/drugsfda/   (public domain, no API key)
Limits:  240 requests/minute and 1,000/day without a key; we make ~30.

We look each drug up by its FDA application number (stored by hand in
data/manual/drugs.csv). We never search by name, because openFDA sometimes
attaches brand names to the wrong application, and one molecule can have
several applications.

Cell and gene therapies regulated by FDA's CBER are NOT in openFDA; their
dates live in data/manual/us_fda.csv instead.
"""
from __future__ import annotations

import json
import time

from common import http_get, load_drugs, save_raw

API = "https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{app}%22&limit=1"


def main() -> None:
    for drug in load_drugs():
        app = drug["fda_application"].strip()
        if not app:
            print(f"  skip {drug['drug_id']}: no openFDA application (CBER product or withdrawn; entered manually)")
            continue
        url = API.format(app=app)
        payload = json.loads(http_get(url))
        result = payload["results"][0]
        # Keep only what we use, so the stored file changes only when it matters.
        trimmed = {
            "application_number": result["application_number"],
            "sponsor_name": result.get("sponsor_name"),
            "brand_names": sorted({p.get("brand_name", "") for p in result.get("products", [])}),
            "original_submissions": [
                {
                    "submission_type": s.get("submission_type"),
                    "submission_status": s.get("submission_status"),
                    "submission_status_date": s.get("submission_status_date"),
                    "review_priority": s.get("review_priority"),
                }
                for s in result.get("submissions", [])
                if s.get("submission_type") == "ORIG"
            ],
        }
        content = (json.dumps(trimmed, indent=2) + "\n").encode()
        retrieved = save_raw(f"fda/{app}.json", content, url)
        print(f"  ok   {drug['drug_id']:<10} {app}  (retrieved {retrieved})")
        time.sleep(0.5)  # be polite to the API


if __name__ == "__main__":
    print("Fetching openFDA ...")
    main()
