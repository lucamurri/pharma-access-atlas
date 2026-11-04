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
            "cms_list_year": v("cms_list_price_year"),
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


def days(x) -> int:
    """Round a median of days for display (half-days round up)."""
    return int(x + 0.5)


def findings(rows: list[dict], s: dict) -> dict:
    """Numbers behind the Insights page.

    The written findings make claims such as "faster" or "more than twice as long".
    Each claim has a guard below. If a data refresh makes a claim untrue, the
    build stops and asks for the text to be rewritten, instead of publishing
    a sentence the data no longer supports.
    """
    from datetime import date

    reimbursed = [r for r in rows if r["it_lag"] is not None]

    def it_median(pred):
        values = [r["it_lag"] for r in reimbursed if pred(r)]
        return (median(values), len(values))

    # 1. Approval is not access
    fda_to_it = median([(date.fromisoformat(r["it_date"]) - date.fromisoformat(r["fda_date"])).days
                        for r in reimbursed])

    # 2. Orphan status
    orph, orph_n = it_median(lambda r: r["orphan_any"] == "yes")
    non, non_n = it_median(lambda r: r["orphan_any"] == "no")
    eu_orph, eu_orph_n = it_median(lambda r: r["eu_orphan"] == "yes")
    eu_non, eu_non_n = it_median(lambda r: r["eu_orphan"] == "no")

    # 3. Germany: comparator route vs orphan route
    comparator = [r for r in rows if r["gba_orphan"] == "no"]
    comparator_nab = [r for r in comparator if r["gba_rating"] == "no added benefit"]
    orphan_route = [r for r in rows if r["gba_orphan"] == "yes"]
    orphan_route_benefit = [r for r in orphan_route if r["gba_rating"] in ("major", "considerable", "minor", "non-quantifiable")]

    # 4. Germany's verdict vs Italian speed
    high, high_n = it_median(lambda r: r["gba_rating"] in ("major", "considerable"))
    nab, nab_n = it_median(lambda r: r["gba_rating"] == "no added benefit")

    # 5. Therapy area and conditional approval
    area = s["it_lag_by_area"]
    slowest = sorted(area, key=lambda a: -area[a]["median"])
    cond, cond_n = it_median(lambda r: r["eu_conditional"] == "yes")
    std, std_n = it_median(lambda r: r["eu_conditional"] == "no")

    # 6. Semaglutide
    by_id = {r["id"]: r for r in rows}
    ryb, weg = by_id["rybelsus"], by_id["wegovy"]

    f = {
        "fda_to_it_median": days(fda_to_it), "it_n": len(reimbursed),
        "orph_it": days(orph), "orph_n": orph_n, "non_it": days(non), "non_n": non_n,
        "eu_orph_it": days(eu_orph), "eu_orph_n": eu_orph_n, "eu_non_it": days(eu_non), "eu_non_n": eu_non_n,
        "eu_orph_gap": days(eu_non) - days(eu_orph),
        "comp_n": len(comparator), "comp_nab_n": len(comparator_nab),
        "comp_nab_pct": round(100 * len(comparator_nab) / len(comparator)),
        "orphan_route_n": len(orphan_route), "orphan_route_benefit_n": len(orphan_route_benefit),
        "high_it": days(high), "high_n": high_n, "nab_it": days(nab), "nab_n": nab_n,
        "high_gap": days(nab) - days(high),
        "rare_it": days(area["Rare disease"]["median"]), "rare_n": area["Rare disease"]["n"],
        "onc_it": days(area["Oncology"]["median"]), "onc_n": area["Oncology"]["n"],
        "cardio_it": days(area["Cardiometabolic"]["median"]), "cardio_n": area["Cardiometabolic"]["n"],
        "cond_it": days(cond), "cond_n": cond_n, "std_it": days(std), "std_n": std_n,
        "cms_mfp": ryb["cms_mfp"], "cms_list": ryb["cms_list"], "cms_discount": days(ryb["cms_discount"]),
        "cms_list_year": ryb["cms_list_year"], "cms_ipay": ryb["cms_ipay"],
        "carvykti_it": by_id["carvykti"]["it_lag"], "zolgensma_it": by_id["zolgensma"]["it_lag"],
        "ryb_it": ryb["it_lag"], "weg_waiting": weg["it_waiting"], "weg_checked": weg["it_checked"],
    }

    guards = {
        "1: national step > 2x regulatory gap": s["it_lag_median"] > 2 * s["lag_median"],
        "1: end-to-end median over two years": fda_to_it > 730,
        "2: Carvykti is the longest Italian wait": max(reimbursed, key=lambda r: r["it_lag"])["id"] == "carvykti",
        "2: Zolgensma among the 3 fastest": by_id["zolgensma"] in sorted(reimbursed, key=lambda r: r["it_lag"])[:3],
        "3: most orphan-route ratings non-quantifiable": sum(r["gba_rating"] == "non-quantifiable" for r in orphan_route) * 2 > len(orphan_route),
        "2: orphan vs non-orphan within 30 days": abs(f["orph_it"] - f["non_it"]) <= 30,
        "2: EU orphan faster than non-EU-orphan": f["eu_orph_it"] < f["eu_non_it"],
        "3: every orphan-route drug got a benefit rating": f["orphan_route_benefit_n"] == f["orphan_route_n"],
        "3: most comparator-route drugs got no added benefit": f["comp_nab_n"] * 2 > f["comp_n"],
        "4: high G-BA rating reimbursed faster in Italy": f["high_it"] < f["nab_it"],
        "5: rare disease fastest area in Italy": slowest[-1] == "Rare disease",
        "5: oncology and cardiometabolic slowest areas": set(slowest[:2]) == {"Oncology", "Cardiometabolic"},
        "5: conditional approvals slower in Italy": f["cond_it"] > f["std_it"],
        "6: Rybelsus reimbursed, Wegovy not": ryb["it_status"] == "reimbursed" and weg["it_status"] == "not reimbursed",
        "6: Wegovy not assessed, Rybelsus no added benefit": weg["gba_rating"] == "not assessed" and ryb["gba_rating"] == "no added benefit",
    }
    broken = [name for name, ok in guards.items() if not ok]
    if broken:
        raise SystemExit("These findings are no longer supported by the data; rewrite "
                         "site/pages/insights.html:\n  " + "\n  ".join(broken))
    return f


if __name__ == "__main__":
    s = summary(flat_rows(load()))
    print(json.dumps(s, indent=2))
    print(json.dumps(chart_titles(s), indent=2))
