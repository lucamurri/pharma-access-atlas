"""Fetch Medicare Drug Price Negotiation data from CMS.

Source:  CMS "Selected Drug List and Negotiated Prices (MFP) data file"
         linked from https://www.cms.gov/initiatives/medicare-prescription-drug-affordability/
         overview/medicare-drug-price-negotiation-program/selected-drugs-negotiated-prices
Terms:   US government work, public domain.

The file name includes its publication date and changes with each update, so
we read the CMS page to find the current link rather than hard-coding it.
The file lists every selected drug and its Maximum Fair Price (MFP) per
30-day equivalent supply. List prices are NOT in this file. They appear
only in CMS's PDF fact sheets, so they are entered in data/manual/cms_list_prices.csv.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile

from common import CACHE, http_get, save_raw

PAGE = ("https://www.cms.gov/initiatives/medicare-prescription-drug-affordability/overview/"
        "medicare-drug-price-negotiation-program/selected-drugs-negotiated-prices")
LINK_PATTERN = re.compile(r'href="([^"]*maximum-fair-price-data-file[^"]*\.zip)"', re.I)

# Columns we keep from the CMS file.
KEEP = ["IPAY", "Selected Drug Name", "Active Ingredient Name or Active Moiety Name",
        "MFP Effective Date", "MFP End Date", "Single MFP per 30 DES", "As of Date",
        "Type of Update", "Remarks"]


def main() -> None:
    html = http_get(PAGE).decode("utf-8", errors="replace")
    match = LINK_PATTERN.search(html)
    if not match:
        raise SystemExit("Could not find the MFP data file link on the CMS page")
    zip_url = match.group(1)
    if zip_url.startswith("/"):
        zip_url = "https://www.cms.gov" + zip_url

    blob = http_get(zip_url)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "cms_mfp.zip").write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8-sig")

    # The file has one row per NDC (package). We collapse it to one row per
    # drug, IPAY and price period: that is all the dashboard needs.
    rows = {}
    for r in csv.DictReader(io.StringIO(text)):
        key = (r["IPAY"], r["Selected Drug Name"], r["MFP Effective Date"], r["Single MFP per 30 DES"])
        rows.setdefault(key, {k: r.get(k, "") for k in KEEP})
    ordered = sorted(rows.values(), key=lambda r: (r["IPAY"], r["Selected Drug Name"], r["MFP Effective Date"]))

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=KEEP, lineterminator="\n")
    writer.writeheader()
    writer.writerows(ordered)
    retrieved = save_raw("cms/selected_drugs_mfp.csv", out.getvalue().encode(), zip_url)
    print(f"  ok   {len(ordered)} CMS drug/price rows from {zip_url.rsplit('/', 1)[-1]} (retrieved {retrieved})")


if __name__ == "__main__":
    print("Fetching CMS ...")
    main()
