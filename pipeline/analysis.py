"""Headline numbers computed from data/processed/drugs.json.

Every KPI, chart title and finding on the site comes from this file, so the
words on the page always match the data. If the data changes, the titles change.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

from common import PROCESSED

G_BA_ORDER = ["major", "considerable", "minor", "non-quantifiable", "no added benefit", "lesser"]


def load() -> dict:
    return json.loads((PROCESSED / "drugs.json").read_text())


def flat_rows(data: dict) -> list[dict]:
    """One flat row per drug: what the explorer table and charts need."""
    rows = []
    for d in data["drugs"]:
        f = d["fields"]

        def v(name):
            return (f.get(name) or {}).get("value")

        fda, ec = v("fda_approval_date"), v("ec_approval_date")
        it = f["it_gu_date"]
        if it["value"]:
            it_status = "reimbursed"
        elif it["status"] == "not_reimbursed_as_of":
            it_status = "not reimbursed"
        else:
            it_status = "unknown"
        gba = f["de_gba_rating_best"]
        rows.append({
            "id": d["drug_id"],
            "brand_us": v("brand_us"), "brand_eu": v("brand_eu"), "inn": v("inn"),
            "company": v("company"), "area": v("therapy_area"),
            "fda_date": fda, "ec_date": ec,
            "first_year": min(fda, ec)[:4] if fda and ec else None,
            "lag": v("us_eu_lag_days"), "first_region": v("first_region"),
            "it_date": it["value"], "it_status": it_status, "it_class": v("it_reimbursement_class"),
            "it_lag": v("it_access_lag_days"), "it_waiting": v("it_days_waiting"),
            "it_checked": it.get("retrieved_date"),
            "gba_date": v("de_gba_decision_date"), "gba_lag": v("de_gba_lag_days"),
            "gba_rating": gba["value"] or ("not assessed" if gba["status"] == "not_assessed" else None),
            "gba_any_nab": v("de_gba_any_no_added_benefit"), "gba_orphan": v("de_gba_orphan_route"),
            "us_orphan": v("us_orphan_designated"), "eu_orphan": v("eu_orphan"),
            "orphan_any": "yes" if "yes" in (v("us_orphan_designated"), v("eu_orphan")) else "no",
            "eu_conditional": v("eu_conditional"), "atmp": v("eu_atmp"),
            "cms_selected": v("cms_selected"), "cms_ipay": v("cms_ipay"),
            "cms_mfp": v("cms_mfp_30day"), "cms_list": v("cms_list_price_30day"),
            "cms_discount": v("cms_discount_pct"),
        })
    return rows


def median(values):
    values = [x for x in values if x is not None]
    return statistics.median(values) if values else None


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    lags = [r["lag"] for r in rows if r["lag"] is not None]
    reimbursed = [r for r in rows if r["it_lag"] is not None]
    waiting = [r for r in rows if r["it_status"] == "not reimbursed"]
    assessed = [r for r in rows if r["gba_rating"] in G_BA_ORDER]
    nab = [r for r in assessed if r["gba_rating"] == "no added benefit"]
    ratings = {k: sum(1 for r in assessed if r["gba_rating"] == k) for k in G_BA_ORDER}

    by_area = defaultdict(list)
    for r in reimbursed:
        by_area[r["area"]].append(r["it_lag"])

    return {
        "n": n,
        "lag_median": median(lags),
        "lag_us_first": sum(1 for x in lags if x > 0),
        "lag_eu_first": sum(1 for x in lags if x < 0),
        "lag_same_day": sum(1 for x in lags if x == 0),
        "it_n_reimbursed": len(reimbursed),
        "it_lag_median": median([r["it_lag"] for r in reimbursed]),
        "it_n_waiting": len(waiting),
        "it_waiting": [{"id": r["id"], "brand": r["brand_eu"], "days": r["it_waiting"]} for r in waiting],
        "it_lag_by_area": {a: {"median": median(v), "n": len(v)} for a, v in sorted(by_area.items())},
        "gba_n_assessed": len(assessed),
        "gba_n_no_added_benefit": len(nab),
        "gba_pct_no_added_benefit": round(100 * len(nab) / len(assessed)) if assessed else None,
        "gba_ratings": ratings,
        "gba_lag_median": median([r["gba_lag"] for r in rows]),
        "cms_n_selected": sum(1 for r in rows if r["cms_selected"] == "yes"),
    }


def chart_titles(s: dict) -> dict:
    """Takeaway titles: each states what the chart shows, not just the metric."""
    waiting = s["it_n_waiting"]
    return {
        "lag": (f"The US approved {s['lag_us_first']} of {s['n']} drugs first; "
                f"the median EU approval came {s['lag_median']:.0f} days after the FDA's"),
        "italy": (f"Italian reimbursement came a median {s['it_lag_median']:.0f} days after EU approval"
                  + (f", and {waiting} drug{'s' if waiting != 1 else ''} {'are' if waiting != 1 else 'is'} still waiting"
                     if waiting else "")),
        "gba": (f"{s['gba_n_no_added_benefit']} of {s['gba_n_assessed']} drugs showed no added benefit "
                f"for any patient group in Germany's first assessment"),
    }


if __name__ == "__main__":
    s = summary(flat_rows(load()))
    print(json.dumps(s, indent=2))
    print(json.dumps(chart_titles(s), indent=2))
