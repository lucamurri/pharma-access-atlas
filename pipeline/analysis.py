"""Headline numbers computed from data/processed/drugs.json.

Every KPI, chart title and finding on the site comes from this file, so the
words on the page always match the data. If the data changes, the titles change.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date

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

        def st(name):
            return (f.get(name) or {}).get("status")

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
            "id": d["drug_id"], "cohort": v("cohort"),
            "brand_us": v("brand_us") or v("brand_eu"), "brand_eu": v("brand_eu"), "inn": v("inn"),
            "company": v("company"), "area": v("therapy_area"), "eu_status": v("eu_status"),
            "fda_date": fda, "ec_date": ec,
            "first_year": min(fda, ec)[:4] if fda and ec else None,
            "lag": v("us_eu_lag_days"), "first_region": v("first_region"),
            "it_date": it["value"], "it_status": it_status, "it_class": v("it_reimbursement_class"),
            "it_lag": v("it_access_lag_days"), "it_waiting": v("it_days_waiting"),
            "it_checked": it.get("retrieved_date"),
            "gba_date": v("de_gba_decision_date"), "gba_lag": v("de_gba_lag_days"),
            "gba_rating": gba["value"] or ("not assessed" if gba["status"] == "not_assessed" else None),
            "gba_any_nab": v("de_gba_any_no_added_benefit"), "gba_orphan": v("de_gba_orphan_route"),
            "fr_date": v("fr_has_date"), "fr_lag": v("fr_has_lag_days"),
            "fr_smr": v("fr_has_smr_best"), "fr_asmr": v("fr_has_asmr_best"),
            # France's verdict: the ASMR, or "SMR insufficient" when HAS found the drug not worth
            # reimbursing for any indication (then no ASMR is given). Both V and that are negative.
            "fr_verdict": v("fr_has_asmr_best") or ("SMR insufficient" if v("fr_has_smr_best") == "insufficient" else None),
            "fr_any_insufficient": v("fr_has_any_insufficient"),
            "en_decision": v("en_nice_decision"), "en_date": v("en_nice_date"), "en_lag": v("en_nice_lag_days"),
            "en_ta": v("en_nice_ta"),
            "us_orphan": v("us_orphan_designated"), "eu_orphan": v("eu_orphan"),
            "orphan_any": ("yes" if "yes" in (v("us_orphan_designated"), v("eu_orphan"))
                           else "no" if st("us_orphan_designated") == "verified" else None),
            "eu_conditional": v("eu_conditional"), "atmp": v("eu_atmp"),
            "cms_selected": v("cms_selected"), "cms_ipay": v("cms_ipay"),
            "cms_mfp": v("cms_mfp_30day"), "cms_list": v("cms_list_price_30day"),
            "cms_list_year": v("cms_list_price_year"),
            "cms_discount": v("cms_discount_pct"),
            "km": {k: time_to(f, a, b) for k, (a, b) in MILESTONES.items()},
            # Confirmed "not yet" (assessment in progress, or none so far) as opposed to never checked.
            "gba_pending": st("de_gba_decision_date") == "not_reimbursed_as_of",
            "fr_pending": st("fr_has_date") in ("not_reimbursed_as_of", "not_assessed"),
            "en_pending": st("en_nice_date") == "not_reimbursed_as_of",
        })
    return rows


# ---------------------------------------------------------------------------
# Time to access, counting drugs that are still waiting.
#
# A median over drugs that already reached a milestone ignores the ones still
# waiting, and those are the slowest, so it understates the delay. The
# Kaplan-Meier method keeps every drug: a drug with a dated milestone is an
# "event"; a drug confirmed as not there yet (status not_reimbursed_as_of or
# not_assessed) counts as waiting until the day it was checked ("censored").
# Drugs never checked (status unknown) are left out.
MILESTONES = {
    "it": ("ec_approval_date", "it_gu_date"),
    "de": ("ec_approval_date", "de_gba_decision_date"),
    "fr": ("ec_approval_date", "fr_has_date"),
    "en": ("ec_approval_date", "en_nice_date"),
    "it_from_fda": ("fda_approval_date", "it_gu_date"),
}


def _gap(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def time_to(f: dict, start_field: str, end_field: str):
    """(days, 1) if the milestone happened, (days so far, 0) if confirmed not yet, else None."""
    start = (f.get(start_field) or {}).get("value")
    end = f.get(end_field) or {}
    if not start:
        return None
    if end.get("value"):
        return [_gap(start, end["value"]), 1]
    if end.get("status") in ("not_reimbursed_as_of", "not_assessed") and end.get("retrieved_date"):
        return [_gap(start, end["retrieved_date"]), 0]
    return None


def kaplan_meier(pairs: list) -> dict:
    """Share of drugs that reached the milestone by each day (1 - survival)."""
    pairs = sorted(p for p in pairs if p is not None)
    at_risk, surv, steps, i = len(pairs), 1.0, [[0, 0.0]], 0
    while i < len(pairs):
        t = pairs[i][0]
        events = sum(1 for p in pairs if p[0] == t and p[1] == 1)
        leaving = sum(1 for p in pairs if p[0] == t)
        if events:
            surv *= 1 - events / at_risk
            steps.append([t, round(100 * (1 - surv), 1)])
        at_risk -= leaving
        i += leaving

    def reached_by(day):
        return max((pct for t, pct in steps if t <= day), default=0.0)

    med = next((t for t, pct in steps if pct >= 50), None)
    return {
        "n": len(pairs), "events": sum(p[1] for p in pairs), "waiting": sum(1 for p in pairs if p[1] == 0),
        "median": med, "pct_1y": reached_by(365), "pct_2y": reached_by(730),
        "max_followup": max((p[0] for p in pairs), default=None), "steps": steps,
    }


def access_curves(all_rows: list[dict]) -> dict:
    rows = core(all_rows)
    return {k: kaplan_meier([r["km"][k] for r in rows]) for k in MILESTONES}


FR_ORDER = ["I", "II", "III", "IV", "V", "SMR insufficient"]
FR_NEGATIVE = ("V", "SMR insufficient")


def core(rows: list[dict]) -> list[dict]:
    """Headline statistics use only drugs selected by the inclusion rule."""
    return [r for r in rows if r["cohort"] == "core"]


def median(values):
    values = [x for x in values if x is not None]
    return statistics.median(values) if values else None


def pct(part, whole):
    return round(100 * part / whole) if whole else None


NICE_POSITIVE = ("recommended", "optimised", "managed access")
NICE_APPRAISED = NICE_POSITIVE + ("not recommended", "terminated")


def summary(all_rows: list[dict]) -> dict:
    rows = core(all_rows)
    n = len(rows)
    lags = [r["lag"] for r in rows if r["lag"] is not None]
    reimbursed = [r for r in rows if r["it_lag"] is not None]
    waiting = [r for r in rows if r["it_status"] == "not reimbursed"]
    assessed = [r for r in rows if r["gba_rating"] in G_BA_ORDER]
    nab = [r for r in assessed if r["gba_rating"] == "no added benefit"]
    ratings = {k: sum(1 for r in assessed if r["gba_rating"] == k) for k in G_BA_ORDER}
    fr = [r for r in rows if r["fr_verdict"]]
    nice = [r for r in rows if r["en_decision"] in NICE_APPRAISED]

    by_area = defaultdict(list)
    for r in reimbursed:
        by_area[r["area"]].append(r["it_lag"])

    return {
        "n": n, "n_reference": len(all_rows) - n,
        "lag_median": median(lags),
        "lag_us_first": sum(1 for x in lags if x > 0),
        "lag_eu_first": sum(1 for x in lags if x < 0),
        "lag_same_day": sum(1 for x in lags if x == 0),
        "it_n_reimbursed": len(reimbursed),
        "it_lag_median": median([r["it_lag"] for r in reimbursed]),
        "it_n_waiting": len(waiting),
        "it_n_unknown": sum(1 for r in rows if r["it_status"] == "unknown"),
        "it_waiting": [{"id": r["id"], "brand": r["brand_eu"], "days": r["it_waiting"]} for r in waiting],
        "it_lag_by_area": {a: {"median": median(v), "n": len(v)} for a, v in sorted(by_area.items())},
        "gba_n_assessed": len(assessed),
        "gba_n_no_added_benefit": len(nab),
        "gba_pct_no_added_benefit": pct(len(nab), len(assessed)),
        "gba_ratings": ratings,
        "gba_lag_median": median([r["gba_lag"] for r in rows]),
        "fr_n": len(fr),
        "fr_asmr": {k: sum(1 for r in fr if r["fr_verdict"] == k) for k in FR_ORDER},
        "fr_pct_negative": pct(sum(1 for r in fr if r["fr_verdict"] in FR_NEGATIVE), len(fr)),
        "fr_lag_median": median([r["fr_lag"] for r in rows]),
        "en_n": len(nice),
        "en_decisions": {k: sum(1 for r in nice if r["en_decision"] == k) for k in NICE_APPRAISED},
        "en_pct_positive": pct(sum(1 for r in nice if r["en_decision"] in NICE_POSITIVE), len(nice)),
        "en_lag_median": median([r["en_lag"] for r in rows]),
        "cms_n_selected": sum(1 for r in all_rows if r["cms_selected"] == "yes"),
        "access": access_curves(all_rows),
        "companies": company_scorecard(all_rows),
    }


# ---------------------------------------------------------------------------
# Company scorecard: the same measures as the rest of the atlas, per company.
SCORECARD_MIN = 5  # companies with fewer drugs are shown only on request (small numbers)


def company_scorecard(all_rows: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in core(all_rows):
        by[r["company"]].append(r)
    out = []
    for name, rs in by.items():
        lags = [r["lag"] for r in rs if r["lag"] is not None]
        it = kaplan_meier([r["km"]["it"] for r in rs])
        rated = [r for r in rs if r["gba_rating"] in G_BA_ORDER]
        fr = [r for r in rs if r["fr_verdict"]]
        en = [r for r in rs if r["en_decision"] in NICE_APPRAISED]
        de_pos = sum(1 for r in rated if r["gba_rating"] not in ("no added benefit", "lesser"))
        fr_pos = sum(1 for r in fr if r["fr_verdict"] not in FR_NEGATIVE)
        en_pos = sum(1 for r in en if r["en_decision"] in NICE_POSITIVE)
        out.append({
            "company": name, "n": len(rs), "drugs": sorted(r["brand_us"] for r in rs),
            "lag_median": median(lags), "eu_first": sum(1 for x in lags if x < 0),
            "it_median": it["median"], "it_n": it["n"], "it_waiting": it["waiting"], "it_events": it["events"],
            "de_pos": de_pos, "de_n": len(rated), "de_pct": pct(de_pos, len(rated)),
            "fr_pos": fr_pos, "fr_n": len(fr), "fr_pct": pct(fr_pos, len(fr)),
            "en_pos": en_pos, "en_n": len(en), "en_pct": pct(en_pos, len(en)),
        })
    return sorted(out, key=lambda c: (-c["n"], c["company"]))


def scorecard_title(s: dict) -> str:
    big = [c for c in s["companies"] if c["n"] >= SCORECARD_MIN]
    timed = [c for c in big if c["it_median"] is not None]
    if not timed:
        return f"{len(big)} companies have at least {SCORECARD_MIN} drugs in the atlas"
    fast = min(timed, key=lambda c: (c["it_median"], c["company"]))
    slow = max(timed, key=lambda c: (c["it_median"], c["company"]))
    return (f"Among the {len(big)} companies with at least {SCORECARD_MIN} drugs, {fast['company']} got half of its "
            f"drugs reimbursed in Italy fastest ({fast['it_median']} days) and {slow['company']} slowest "
            f"({slow['it_median']})")


def chart_titles(s: dict) -> dict:
    """Takeaway titles: each states what the chart shows, not just the metric."""
    a = s["access"]
    steps = {"Germany (G-BA decision)": a["de"]["median"], "France (HAS opinion)": a["fr"]["median"],
             "England (NICE guidance)": a["en"]["median"], "Italy (reimbursement)": a["it"]["median"]}
    known = {k: v for k, v in steps.items() if v is not None}
    slowest = max(known, key=known.get) if known else None
    fastest = min(known, key=known.get) if known else None
    return {
        "lag": (f"The US approved {s['lag_us_first']} of {s['n']} drugs first; "
                f"the median EU approval came {days(s['lag_median'])} days after the FDA's"),
        "countries": (f"After EU approval, {fastest.split(' (')[0]} moves fastest and {slowest.split(' (')[0]} slowest: "
                      f"half of drugs got there within {known[fastest]} vs {known[slowest]} days"
                      if known else "Days after EU approval"),
        "italy": (f"Among the {s['it_n_reimbursed']} drugs Italy reimbursed, the median wait was "
                  f"{days(s['it_lag_median'])} days, varying widely by therapy area"),
        "hta": (f"Germany found no added benefit for {s['gba_pct_no_added_benefit']}% of drugs; "
                f"France found no improvement or no reimbursable value for {s['fr_pct_negative']}%"),
    }


def days(x) -> int:
    """Round a median of days for display (half-days round up)."""
    return int(x + 0.5)


def findings(all_rows: list[dict], s: dict) -> dict:
    """Numbers behind the Insights page (core cohort only, except the semaglutide case).

    The written findings make claims such as "shrinking" or "most". Each claim has a
    guard below. If a data refresh makes a claim untrue, the build stops and asks
    for the text to be rewritten, instead of publishing a sentence the data no
    longer supports.
    """
    from datetime import date

    rows = core(all_rows)
    reimbursed = [r for r in rows if r["it_lag"] is not None]

    def m(values):
        values = [v for v in values if v is not None]
        return (median(values), len(values))

    # 1. Approval is the short part of the wait. Medians come from the time-to-access
    #    curves, so drugs still waiting count (see kaplan_meier above).
    a = s["access"]
    fr, de, en, it, fda_to_it = (a[k]["median"] for k in ("fr", "de", "en", "it", "it_from_fda"))

    # 2. The regulatory gap is shrinking (2019 vs 2022 FDA approvals; later years are cut short by the window)
    lag19, lag19_n = m([r["lag"] for r in rows if r["fda_date"][:4] == "2019"])
    lag22, lag22_n = m([r["lag"] for r in rows if r["fda_date"][:4] == "2022"])

    # 3. Germany: comparator route vs orphan route
    rated = [r for r in rows if r["gba_rating"] in G_BA_ORDER]
    comp = [r for r in rated if r["gba_orphan"] == "no"]
    comp_nab = [r for r in comp if r["gba_rating"] == "no added benefit"]
    orph = [r for r in rated if r["gba_orphan"] == "yes"]
    orph_pos = [r for r in orph if r["gba_rating"] != "no added benefit"]

    # 4. England often funds what Germany rated as no added benefit
    de_nab_en = [r for r in rows if r["gba_rating"] == "no added benefit" and r["en_decision"] in NICE_APPRAISED]
    de_nab_en_pos = [r for r in de_nab_en if r["en_decision"] in NICE_POSITIVE]

    # 5. Germany and France disagree on a large share
    both = [r for r in rows if r["gba_rating"] in G_BA_ORDER and r["fr_verdict"]]
    agree_neg = [r for r in both if r["gba_rating"] == "no added benefit" and r["fr_verdict"] in FR_NEGATIVE]
    agree_pos = [r for r in both if r["gba_rating"] != "no added benefit" and r["fr_verdict"] not in FR_NEGATIVE]
    disagree = len(both) - len(agree_neg) - len(agree_pos)

    # 6. Semaglutide (reference drugs)
    by_id = {r["id"]: r for r in all_rows}
    ryb, weg = by_id["rybelsus"], by_id["wegovy"]

    f = {
        "fda_to_it_median": fda_to_it,
        "fr_med": fr, "fr_n2": a["fr"]["n"], "fr_wait": a["fr"]["waiting"],
        "de_med": de, "de_n2": a["de"]["n"], "de_wait": a["de"]["waiting"],
        "en_med": en, "en_n2": a["en"]["n"], "en_wait": a["en"]["waiting"],
        "it_med": it, "it_n2": a["it"]["n"], "it_wait": a["it"]["waiting"],
        "it_2y": days(a["it"]["pct_2y"]), "de_1y": days(a["de"]["pct_1y"]),
        "lag19": days(lag19), "lag19_n": lag19_n, "lag22": days(lag22), "lag22_n": lag22_n,
        "comp_n": len(comp), "comp_nab_n": len(comp_nab), "comp_nab_pct": pct(len(comp_nab), len(comp)),
        "orph_route_n": len(orph), "orph_route_pos_n": len(orph_pos),
        "de_nab_en_n": len(de_nab_en), "de_nab_en_pos_n": len(de_nab_en_pos),
        "de_nab_en_pos_pct": pct(len(de_nab_en_pos), len(de_nab_en)),
        "both_n": len(both), "disagree_n": disagree, "disagree_pct": pct(disagree, len(both)),
        "agree_neg_n": len(agree_neg), "agree_pos_n": len(agree_pos),
        "cms_mfp": ryb["cms_mfp"], "cms_list": ryb["cms_list"], "cms_discount": days(ryb["cms_discount"]),
        "cms_list_year": ryb["cms_list_year"], "cms_ipay": ryb["cms_ipay"],
        "ryb_it": ryb["it_lag"], "weg_waiting": weg["it_waiting"], "weg_en": weg["en_decision"],
    }

    guards = {
        "1: every curve passes 50% (medians exist)": None not in (fr, de, en, it, fda_to_it),
        "1: Italy is the slowest of the four milestones": it == max(fr, de, en, it),
        "1: France is the fastest of the four milestones": fr == min(fr, de, en, it),
        "1: Italy's step is more than twice the US-EU gap": it > 2 * s["lag_median"],
        "1: end-to-end median is 'more than two years' (24-36 months)": 730 <= fda_to_it < 1095,
        "2: 2022 gap shorter than 2019 gap": lag22 < lag19,
        "3: most comparator-route drugs got no added benefit": len(comp_nab) * 2 > len(comp),
        "3: every orphan-route drug got a benefit rating": len(orph_pos) == len(orph),
        "4: most German 'no added benefit' drugs got a positive NICE decision": len(de_nab_en_pos) * 2 > len(de_nab_en),
        "5: at least a third of Germany-France pairs disagree": disagree * 3 >= len(both),
        "6: Rybelsus reimbursed in Italy, Wegovy not": ryb["it_status"] == "reimbursed" and weg["it_status"] == "not reimbursed",
        "6: Wegovy not assessed in Germany, Rybelsus no added benefit":
            weg["gba_rating"] == "not assessed" and ryb["gba_rating"] == "no added benefit",
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
