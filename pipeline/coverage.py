"""Coverage report: how much of each source's data is actually filled in.

For each source we count (drug x field) cells and classify them as:
  filled        - a sourced value
  checked, none - we checked and the answer is "not yet" (e.g. not reimbursed)
  unknown       - not yet researched or not verifiable

CMS price fields only apply to drugs selected for negotiation, so they are
counted only for those drugs.

Output: a Markdown table printed to the screen and data/processed/coverage.json
"""
from __future__ import annotations

import json
from collections import defaultdict

from common import PROCESSED, write_json
from fields import FIELDS

ORDER = ["Identity", "FDA", "EMA", "Italy", "Germany", "France", "England", "CMS", "Calculated"]
CMS_PRICE_FIELDS = {"cms_ipay", "cms_mfp_30day", "cms_list_price_30day", "cms_list_price_year"}
# Calculated fields that only apply in some situations (e.g. a lag needs two dates).
CONDITIONAL = {"it_days_waiting", "cms_discount_pct", "it_access_lag_days", "de_gba_lag_days",
               "fr_has_lag_days", "en_nice_lag_days"}


def main() -> None:
    data = json.loads((PROCESSED / "drugs.json").read_text())
    stats = defaultdict(lambda: {"fields": set(), "cells": 0, "filled": 0, "checked_none": 0, "unknown": 0})

    for drug in data["drugs"]:
        f = drug["fields"]
        selected = f["cms_selected"]["value"] == "yes"
        for name, meta in FIELDS.items():
            if name in CMS_PRICE_FIELDS and not selected:
                continue
            if name in CONDITIONAL:
                continue  # reported separately below
            s = stats[meta["group"]]
            s["fields"].add(name)
            s["cells"] += 1
            obj = f.get(name)
            if obj and obj.get("value") is not None:
                s["filled"] += 1
            elif obj and obj.get("status") in ("not_reimbursed_as_of", "not_assessed"):
                s["checked_none"] += 1
            else:
                s["unknown"] += 1

    rows = []
    print("\n| Source | Mode | Fields | Cells | Filled | Checked: not yet / none | Unknown | % filled | % resolved |")
    print("|---|---|---|---|---|---|---|---|---|")
    for group in ORDER:
        s = stats[group]
        modes = sorted({FIELDS[n]["mode"] for n in s["fields"]})
        pct = 100 * s["filled"] / s["cells"] if s["cells"] else 0
        resolved = 100 * (s["filled"] + s["checked_none"]) / s["cells"] if s["cells"] else 0
        rows.append({"group": group, "modes": modes, "fields": len(s["fields"]), "cells": s["cells"],
                     "filled": s["filled"], "checked_none": s["checked_none"], "unknown": s["unknown"],
                     "pct_filled": round(pct, 1), "pct_resolved": round(resolved, 1)})
        print(f"| {group} | {'/'.join(modes)} | {len(s['fields'])} | {s['cells']} | {s['filled']} | "
              f"{s['checked_none']} | {s['unknown']} | {pct:.0f}% | {resolved:.0f}% |")

    # Per-field detail for the manual fields, which is where gaps live.
    detail = {}
    for name, meta in FIELDS.items():
        if meta["mode"] != "manual" or meta["group"] == "Identity":
            continue
        counts = defaultdict(int)
        for drug in data["drugs"]:
            obj = drug["fields"].get(name)
            if obj is None:
                continue
            counts["filled" if obj.get("value") is not None else obj.get("status", "unknown")] += 1
        detail[name] = dict(counts)
    print("\nManual fields, by status:")
    for name, counts in detail.items():
        print(f"  {name:<30} " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    write_json(PROCESSED / "coverage.json", {"data_as_of": data["data_as_of"], "groups": rows, "manual_fields": detail})


if __name__ == "__main__":
    main()
