"""Headline numbers computed from data/processed/drugs.json.

Every KPI, chart title and finding on the site comes from this file, so the
words on the page always match the data. If the data changes, the titles change.
"""
from __future__ import annotations

import json
import math
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
            "fda_priority": v("fda_review_priority"),
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
            # Why a drug has no verdict yet: not_assessed (no procedure), not_reimbursed_as_of
            # (procedure in progress) or unknown (not verified).
            "gba_status": gba["status"], "fr_status": st("fr_has_date"), "en_status": st("en_nice_decision"),
            "it_innov": v("it_innovative"), "it_price_date": v("it_price_opinion_date"),
            "it_admin": v("it_admin_days"),
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
    # Sensitivity: Italy measured at the AIFA price opinion (CPR/CSE) instead of GU publication
    "it_price": ("ec_approval_date", "it_price_opinion_date"),
    # The US page counts from FDA approval: how far behind the US each European milestone came.
    "ec_from_fda": ("fda_approval_date", "ec_approval_date"),
    "de_from_fda": ("fda_approval_date", "de_gba_decision_date"),
    "fr_from_fda": ("fda_approval_date", "fr_has_date"),
    "en_from_fda": ("fda_approval_date", "en_nice_date"),
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


def _ci(surv: float, greenwood: float, z: float = 1.959964) -> list | None:
    """95% confidence interval, in percent, for the share reached (1 - survival).

    Greenwood's variance with the log(-log) transform, the default in the lifelines
    library, which keeps the interval between 0% and 100%.
    """
    if not 0 < surv < 1:
        return None
    se = math.sqrt(greenwood) / abs(math.log(surv))
    theta = math.log(-math.log(surv))
    s_high, s_low = (math.exp(-math.exp(theta + k * z * se)) for k in (-1, 1))
    return [round(100 * (1 - s_high), 1), round(100 * (1 - s_low), 1)]


def kaplan_meier(pairs: list) -> dict:
    """Share of drugs that reached the milestone by each day (1 - survival)."""
    pairs = sorted(p for p in pairs if p is not None)
    at_risk, surv, steps, i = len(pairs), 1.0, [[0, 0.0]], 0
    greenwood, surv_2y, greenwood_2y = 0.0, 1.0, 0.0
    while i < len(pairs):
        t = pairs[i][0]
        events = sum(1 for p in pairs if p[0] == t and p[1] == 1)
        leaving = sum(1 for p in pairs if p[0] == t)
        if events:
            surv *= 1 - events / at_risk
            if at_risk > events:
                greenwood += events / (at_risk * (at_risk - events))
            steps.append([t, round(100 * (1 - surv), 1)])
            if t <= 730:
                surv_2y, greenwood_2y = surv, greenwood
        at_risk -= leaving
        i += leaving

    def reached_by(day):
        return max((pct for t, pct in steps if t <= day), default=0.0)

    med = next((t for t, pct in steps if pct >= 50), None)
    return {
        "n": len(pairs), "events": sum(p[1] for p in pairs), "waiting": sum(1 for p in pairs if p[1] == 0),
        "median": med, "pct_1y": reached_by(365), "pct_2y": reached_by(730), "ci_2y": _ci(surv_2y, greenwood_2y),
        "max_followup": max((p[0] for p in pairs), default=None), "steps": steps,
    }


def log_rank_p(a: list, b: list) -> float | None:
    """Two-sided p-value of the log-rank test: do two groups reach the milestone at different speeds?

    Standard test for Kaplan-Meier curves (one degree of freedom). A small p means the
    difference is unlikely to be chance alone; it says nothing about cause.
    """
    a, b = [p for p in a if p], [p for p in b if p]
    observed = expected = variance = 0.0
    for t in sorted({t for t, e in a + b if e}):
        na, nb = sum(1 for x, _ in a if x >= t), sum(1 for x, _ in b if x >= t)
        da = sum(1 for x, e in a if x == t and e)
        d = da + sum(1 for x, e in b if x == t and e)
        n = na + nb
        if n < 2:
            continue
        observed += da
        expected += d * na / n
        variance += d * (na / n) * (nb / n) * (n - d) / (n - 1)
    if not variance:
        return None
    return math.erfc(math.sqrt((observed - expected) ** 2 / variance / 2))


def access_curves(all_rows: list[dict]) -> dict:
    rows = core(all_rows)
    return {k: kaplan_meier([r["km"][k] for r in rows]) for k in MILESTONES}


COHORT_SPLIT = "2021"  # EC approvals 2019-2021 ("early") vs 2022-2025 ("late")


def access_by_cohort(all_rows: list[dict]) -> dict:
    """Robustness check: the four country curves for early and recent EC approvals.

    Recent drugs are many and often still waiting; if the curves moved a lot between
    the two periods, the headline medians would depend on the mix of years.
    """
    rows = [r for r in core(all_rows) if r["ec_date"]]
    out = {}
    for k in ("fr", "de", "en", "it"):
        groups = {"early": [r["km"][k] for r in rows if r["ec_date"][:4] <= COHORT_SPLIT],
                  "late": [r["km"][k] for r in rows if r["ec_date"][:4] > COHORT_SPLIT]}
        stats = {}
        for g, pairs in groups.items():
            km = kaplan_meier(pairs)
            stats[g] = {f: km[f] for f in ("n", "waiting", "median", "pct_2y", "ci_2y")}
        p = log_rank_p(groups["early"], groups["late"])
        out[k] = {**stats, "p": round(p, 3) if p is not None else None}
    return out


FR_ORDER = ["I", "II", "III", "IV", "V", "SMR insufficient"]
FR_NEGATIVE = ("V", "SMR insufficient")


def core(rows: list[dict]) -> list[dict]:
    """Headline statistics use only drugs selected by the inclusion rule."""
    return [r for r in rows if r["cohort"] == "core"]


IT_INNOV_ORDER = ["full", "conditional", "not recognised"]


def _quartiles(values):
    values = sorted(v for v in values if v is not None)
    if len(values) < 4:
        return {"n": len(values), "median": median(values), "p25": None, "p75": None}
    q = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "median": median(values), "p25": q[0], "p75": q[2]}


def innov_by_verdict(rows: list[dict]) -> dict:
    """Counts only: AIFA innovativeness next to each other country's verdict on the same drug.

    The scales are not comparable (different criteria and comparators), so no agreement
    score is computed; the table just shows how the judgements sit side by side.
    """
    rated = [r for r in rows if r["it_innov"] in IT_INNOV_ORDER]
    groups = {
        "de_benefit": lambda r: _added_benefit(r),
        "fr_benefit": lambda r: "yes" if r["fr_verdict"] in ("I", "II", "III", "IV") else "no" if r["fr_verdict"] else None,
        "en_positive": lambda r: ("yes" if r["en_decision"] in NICE_POSITIVE else "no"
                                   if r["en_decision"] in ("not recommended", "terminated") else None),
    }
    out = {}
    for key, fn in groups.items():
        out[key] = {g: {k: sum(1 for r in rated if fn(r) == g and r["it_innov"] == k) for k in IT_INNOV_ORDER}
                    for g in ("yes", "no")}
    return out


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
        # Drugs without a verdict, by reason (shares above are of drugs with a verdict)
        "gba_none": {k: sum(1 for r in rows if r["gba_rating"] not in G_BA_ORDER and r["gba_status"] == k)
                     for k in ("not_assessed", "not_reimbursed_as_of", "unknown")},
        "fr_none": sum(1 for r in rows if not r["fr_verdict"]),
        "en_none": {"in_progress": sum(1 for r in rows if r["en_decision"] is None and r["en_status"] == "not_reimbursed_as_of"),
                    "not_appraised": sum(1 for r in rows if r["en_decision"] == "not appraised"),
                    "unknown": sum(1 for r in rows if r["en_decision"] is None and r["en_status"] != "not_reimbursed_as_of")},
        "fr_n_v": sum(1 for r in fr if r["fr_verdict"] == "V"),
        "fr_n_smr_insufficient": sum(1 for r in fr if r["fr_verdict"] == "SMR insufficient"),
        "fr_pct_v": pct(sum(1 for r in fr if r["fr_verdict"] == "V"), len(fr)),
        "fr_pct_smr_insufficient": pct(sum(1 for r in fr if r["fr_verdict"] == "SMR insufficient"), len(fr)),
        "gba_n_nq_orphan": sum(1 for r in assessed if r["gba_rating"] == "non-quantifiable" and r["gba_orphan"] == "yes"),
        "en_n_terminated": sum(1 for r in rows if r["en_decision"] == "terminated"),
        # Sensitivity: the English curve if terminated appraisals counted as not yet reached
        "en_terminated_censored": {k: v for k, v in kaplan_meier(
            [[r["km"]["en"][0], 0] if r["en_decision"] == "terminated" and r["km"]["en"] else r["km"]["en"]
             for r in rows]).items() if k in ("median", "pct_2y", "n", "events")},
        "n_all": len(all_rows),
        # AIFA innovativeness, among reimbursed drugs (granted only with reimbursement)
        "it_innov": {k: sum(1 for r in reimbursed if r["it_innov"] == k) for k in IT_INNOV_ORDER},
        "it_innov_unknown": sum(1 for r in reimbursed if r["it_innov"] is None),
        # Administrative phase: AIFA price opinion to GU publication
        "it_admin": _quartiles([r["it_admin"] for r in reimbursed]),
        "it_innov_by_verdict": innov_by_verdict(rows),
        "cms_n_selected": sum(1 for r in all_rows if r["cms_selected"] == "yes"),
        "access": access_curves(all_rows),
        "access_by_cohort": access_by_cohort(all_rows),
        "companies": company_scorecard(all_rows),
        "drivers": italy_drivers(all_rows),
        "countries": country_profiles(all_rows),
        "us": us_profile(all_rows),
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


# ---------------------------------------------------------------------------
# What goes with a faster Italian launch? Each factor splits the drugs in two
# and compares their time-to-reimbursement curves (same method as the overview).
def _added_benefit(r):
    if r["gba_rating"] in ("major", "considerable", "minor", "non-quantifiable"):
        return "yes"
    return "no" if r["gba_rating"] in ("no added benefit", "lesser") else None


DRIVERS = [
    ("orphan", "Orphan drug (US or EU)", "Not orphan", lambda r, big: r["orphan_any"]),
    ("de_benefit", "Added benefit in Germany", "No added benefit in Germany", lambda r, big: _added_benefit(r)),
    ("fr_benefit", "Improvement in France (ASMR I–IV)", "No improvement in France",
     lambda r, big: "yes" if r["fr_verdict"] in ("I", "II", "III", "IV") else "no" if r["fr_verdict"] else None),
    ("conditional", "Conditional EU approval", "Standard EU approval", lambda r, big: r["eu_conditional"]),
    ("atmp", "Cell or gene therapy", "Other medicines", lambda r, big: r["atmp"]),
    ("oncology", "Oncology", "Other therapy areas", lambda r, big: "yes" if r["area"] == "Oncology" else "no"),
    ("large_company", f"Company with {SCORECARD_MIN}+ drugs here", "Smaller company",
     lambda r, big: "yes" if r["company"] in big else "no"),
]


def italy_drivers(all_rows: list[dict]) -> list[dict]:
    rows = core(all_rows)
    big = {c["company"] for c in company_scorecard(all_rows) if c["n"] >= SCORECARD_MIN}
    out = []
    for key, yes_label, no_label, fn in DRIVERS:
        groups = {"yes": [], "no": []}
        for r in rows:
            v = fn(r, big)
            if v in groups:
                groups[v].append(r["km"]["it"])
        stats = {}
        for g, pairs in groups.items():
            km = kaplan_meier(pairs)
            stats[g] = {k: km[k] for k in ("n", "events", "waiting", "median", "pct_1y", "pct_2y", "ci_2y")}
        p = log_rank_p(groups["yes"], groups["no"])
        out.append({"key": key, "yes_label": yes_label, "no_label": no_label, **stats,
                    "p": round(p, 3) if p is not None else None})
    return out


# ---------------------------------------------------------------------------
# Country pages: one profile per national milestone.
COUNTRY_KEYS = ["it", "de", "fr", "en"]


def country_profiles(all_rows: list[dict]) -> dict:
    rows = core(all_rows)
    out = {}
    for k in COUNTRY_KEYS:
        timed = [(r, r["km"][k]) for r in rows if r["km"][k]]
        reached = sorted(((t, r) for r, (t, e) in timed if e), key=lambda x: (x[0], x[1]["brand_us"]))
        waiting = sorted(((t, r) for r, (t, e) in timed if not e), key=lambda x: (-x[0], x[1]["brand_us"]))
        def brief(t, r):
            # Why a drug without a milestone is still counted: in progress, or none at all.
            note = None
            if k == "en" and r["en_decision"] == "not appraised":
                note = "NICE did not appraise it"
            elif k == "de" and r["gba_rating"] == "not assessed":
                note = "no G-BA assessment"
            elif k == "fr" and not r["fr_date"]:
                note = "no HAS opinion when checked"
            return {"id": r["id"], "brand": r["brand_us"], "area": r["area"], "days": t,
                    "eu_status": r["eu_status"], "note": note}

        by_area = defaultdict(list)
        for r, pair in timed:
            by_area[r["area"]].append(pair)
        areas = []
        for area, pairs in by_area.items():
            if len(pairs) >= 5:
                km = kaplan_meier(pairs)
                areas.append({"area": area, "n": km["n"], "waiting": km["waiting"], "median": km["median"],
                              "pct_2y": km["pct_2y"]})
        areas.sort(key=lambda a: (a["median"] is None, a["median"] or 0, a["area"]))

        if k == "it":
            mix = {"A (community pharmacies)": sum(1 for r in rows if r["it_status"] == "reimbursed" and r["it_class"] == "A"),
                   "H (hospital)": sum(1 for r in rows if r["it_status"] == "reimbursed" and r["it_class"] == "H"),
                   "Not reimbursed yet": sum(1 for r in rows if r["it_status"] == "not reimbursed")}
        elif k == "de":
            mix = {g: sum(1 for r in rows if r["gba_rating"] == g) for g in G_BA_ORDER}
        elif k == "fr":
            mix = {("ASMR " + g if g != "SMR insufficient" else g): sum(1 for r in rows if r["fr_verdict"] == g) for g in FR_ORDER}
        else:
            mix = {g: sum(1 for r in rows if r["en_decision"] == g) for g in NICE_APPRAISED}
        out[k] = {
            "fastest": [brief(t, r) for t, r in reached[:5]],
            "slowest": [brief(t, r) for t, r in reached[-5:][::-1]],
            "longest_waiting": [brief(t, r) for t, r in waiting[:5]],
            "areas": areas, "mix": mix,
        }
    return out


def us_profile(all_rows: list[dict]) -> dict:
    """The US page: FDA approval is market entry, so it looks at what Europe did afterwards."""
    rows = core(all_rows)
    timed = [r for r in rows if r["lag"] is not None]
    brief = lambda r: {"id": r["id"], "brand": r["brand_us"], "area": r["area"], "days": r["lag"]}
    by_area = defaultdict(list)
    for r in timed:
        by_area[r["area"]].append(r)
    areas = [{"area": a, "n": len(rs), "median": days(median([r["lag"] for r in rs])),
              "us_first": sum(1 for r in rs if r["lag"] > 0)} for a, rs in by_area.items() if len(rs) >= 5]
    areas.sort(key=lambda a: (-a["median"], a["area"]))
    priority = sum(1 for r in rows if r["fda_priority"] == "Priority")
    reviewed = sum(1 for r in rows if r["fda_priority"] in ("Priority", "Standard"))
    orphan = sum(1 for r in rows if r["us_orphan"] == "yes")
    orphan_known = sum(1 for r in rows if r["us_orphan"] in ("yes", "no"))
    return {
        "n": len(timed), "us_first": sum(1 for r in timed if r["lag"] > 0),
        "pct_us_first": pct(sum(1 for r in timed if r["lag"] > 0), len(timed)),
        "priority": priority, "reviewed": reviewed, "pct_priority": pct(priority, reviewed),
        "orphan": orphan, "orphan_known": orphan_known, "pct_orphan": pct(orphan, orphan_known),
        "mix": {"Priority review": priority, "Standard review": reviewed - priority,
                "Review type not in openFDA": len(rows) - reviewed},
        "areas": areas,
        "eu_first": [brief(r) for r in sorted((r for r in timed if r["lag"] < 0), key=lambda r: (r["lag"], r["brand_us"]))[:5]],
        "longest_gap": [brief(r) for r in sorted(timed, key=lambda r: (-r["lag"], r["brand_us"]))[:5]],
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

    # 1. Four different milestones after EU approval. Medians come from the time-to-access
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

    # 7. Traits compared with Italian reimbursement times (see italy_drivers)
    drv = {d["key"]: d for d in s["drivers"]}
    medians = [d[g]["median"] for d in s["drivers"] for g in ("yes", "no") if d[g]["n"] >= 20 and d[g]["median"]]

    f = {
        "drv_n": len(s["drivers"]), "drv_med_lo": min(medians), "drv_med_hi": max(medians),
        "drv_de_y_med": drv["de_benefit"]["yes"]["median"], "drv_de_n_med": drv["de_benefit"]["no"]["median"],
        "drv_de_y_n": drv["de_benefit"]["yes"]["n"], "drv_de_n_n": drv["de_benefit"]["no"]["n"],
        "drv_or_y_med": drv["orphan"]["yes"]["median"], "drv_or_n_med": drv["orphan"]["no"]["median"],
        "drv_lc_y_2y": days(drv["large_company"]["yes"]["pct_2y"]), "drv_lc_n_2y": days(drv["large_company"]["no"]["pct_2y"]),
        "drv_lc_y_n": drv["large_company"]["yes"]["n"], "drv_lc_n_n": drv["large_company"]["no"]["n"],
        "drv_lc_p": f'{drv["large_company"]["p"]:.2f}',
        # Bonferroni threshold for the driver comparisons, shown as e.g. 0.007
        "drv_alpha": f'{0.05 / len(s["drivers"]):.3f}',
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
        "2: 2022 gap shorter than 2019 gap": lag22 < lag19,
        "3: most comparator-route drugs got no added benefit": len(comp_nab) * 2 > len(comp),
        "3: every orphan-route drug got a benefit rating": len(orph_pos) == len(orph),
        "4: most German 'no added benefit' drugs got a positive NICE decision": len(de_nab_en_pos) * 2 > len(de_nab_en),
        "5: at least a third of Germany-France pairs disagree": disagree * 3 >= len(both),
        "6: Rybelsus reimbursed in Italy, Wegovy not": ryb["it_status"] == "reimbursed" and weg["it_status"] == "not reimbursed",
        "6: Wegovy not assessed in Germany, Rybelsus no added benefit":
            weg["gba_rating"] == "not assessed" and ryb["gba_rating"] == "no added benefit",
        "7: Germany's verdict shows no clear link to Italy's speed (p >= 0.05)": drv["de_benefit"]["p"] >= 0.05,
        "7: orphan status shows no clear link to Italy's speed (p >= 0.05)": drv["orphan"]["p"] >= 0.05,
        "7: company size is the only factor with p < 0.05": [d["key"] for d in s["drivers"] if d["p"] < 0.05] == ["large_company"],
        "7: large companies reach more drugs within two years": drv["large_company"]["yes"]["pct_2y"] > drv["large_company"]["no"]["pct_2y"],
        "methodology: early vs recent approval curves do not differ significantly":
            all(c["p"] is not None and c["p"] >= 0.05 for c in s["access_by_cohort"].values()),
        "methodology: Italy reaches the price opinion before publication (median)":
            None not in (s["access"]["it_price"]["median"], it) and s["access"]["it_price"]["median"] < it,
        "index/methodology: price opinion to publication is never negative":
            all(r["it_admin"] is None or r["it_admin"] >= 0 for r in rows),
        "methodology: every Medicare-selected drug is a reference drug":
            all(r["cohort"] == "reference" for r in all_rows if r["cms_selected"] == "yes"),
        "7: no comparison passes the Bonferroni threshold": all(d["p"] >= 0.05 / len(s["drivers"]) for d in s["drivers"]),
    }
    broken = [name for name, ok in guards.items() if not ok]
    if broken:
        raise SystemExit("These findings are no longer supported by the data; rewrite "
                         "site/pages/insights.html:\n  " + "\n  ".join(broken))
    return f


if __name__ == "__main__":
    s = summary(flat_rows(load()))
    print(json.dumps(s, indent=2))
