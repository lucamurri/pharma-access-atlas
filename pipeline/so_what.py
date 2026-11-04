"""Three 'so what' bullets per drug brief, generated from the data.

With ~200 drugs the bullets are written by rules instead of by hand, so every
sentence is grounded in the drug's own sourced values and in medians for the
whole atlas. The wording is cautious ("faster than the median") and never adds
facts that are not in the data. check_text.py then verifies every number.
"""
from __future__ import annotations

import analysis

RATING_TEXT = {
    "major": "major added benefit", "considerable": "considerable added benefit",
    "minor": "minor added benefit", "non-quantifiable": "added benefit that could not be quantified",
    "no added benefit": "no added benefit for any patient group", "lesser": "lesser benefit than existing therapy",
}
ASMR_TEXT = {"I": "major improvement (ASMR I)", "II": "important improvement (ASMR II)",
             "III": "moderate improvement (ASMR III)", "IV": "minor improvement (ASMR IV)",
             "V": "no improvement over existing care (ASMR V)"}
NICE_TEXT = {"recommended": "recommended it", "optimised": "recommended it for a narrower group than licensed",
             "managed access": "recommended it with managed access (e.g. Cancer Drugs Fund)",
             "not recommended": "did not recommend it", "terminated": "terminated its appraisal (no company submission)",
             "not appraised": "has not appraised it"}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def bullets(r: dict, all_rows: list[dict], s: dict) -> list[str]:
    core = analysis.core(all_rows)
    out = []

    # 1. Regulatory timing ----------------------------------------------------
    lag, med = r["lag"], analysis.days(s["lag_median"])
    if lag is None:
        out.append("US and EU approval dates are not both available.")
    elif lag > 0:
        cmp = "longer than" if lag > med else "shorter than" if lag < med else "the same as"
        out.append(f"EU approval came {lag:,} days after the FDA's, {cmp} the atlas median of {med} days.")
    elif lag < 0:
        out.append(f"Europe approved it first, {-lag:,} days before the FDA: one of {s['lag_eu_first']} "
                   f"drugs in the atlas approved in the EU first.")
    else:
        out.append("The FDA and the European Commission approved it on the same day.")

    # 2. Italian access ---------------------------------------------------------
    it_med = s["access"]["it"]["median"]  # counts drugs still waiting
    reimbursed = sorted([x for x in core if x["it_lag"] is not None], key=lambda x: -x["it_lag"])
    if r["it_lag"] is not None:
        rank = next((i + 1 for i, x in enumerate(reimbursed) if x["id"] == r["id"]), None)
        quartile = ""
        if rank and rank <= len(reimbursed) // 4:
            quartile = f", the {ordinal(rank)}-longest wait of {len(reimbursed)}"
        elif rank and rank > len(reimbursed) - len(reimbursed) // 4:
            quartile = f", the {ordinal(len(reimbursed) - rank + 1)}-fastest of {len(reimbursed)}"
        cmp = "slower than" if r["it_lag"] > it_med else "faster than" if r["it_lag"] < it_med else "equal to"
        out.append(f"Italy reimbursed it (class {r['it_class']}) {r['it_lag']:,} days after EU approval, "
                   f"{cmp} the median of {it_med} days{quartile}.")
    elif r["it_status"] == "not reimbursed":
        out.append(f"Italy had not reimbursed it {r['it_waiting']:,} days after EU approval "
                   f"(class {r['it_class']}, checked {r['it_checked']}).")
    else:
        out.append("Its Italian reimbursement status could not be verified from public sources.")

    # 3. Value verdicts across Germany, France and England -----------------------
    parts = []
    if r["gba_rating"] in RATING_TEXT:
        parts.append(f"Germany's G-BA found {RATING_TEXT[r['gba_rating']]}"
                     + (" (orphan rules)" if r["gba_orphan"] == "yes" else ""))
    elif r["gba_rating"] == "not assessed":
        parts.append("Germany's G-BA has no benefit assessment for it")
    if r["fr_asmr"]:
        parts.append(f"France's HAS rated it {ASMR_TEXT[r['fr_asmr']]}")
    elif r["fr_verdict"] == "SMR insufficient":
        parts.append("France's HAS found its benefit insufficient to justify reimbursement")
    if r["en_decision"]:
        parts.append(f"England's NICE {NICE_TEXT[r['en_decision']]}")
    if parts:
        sentence = "; ".join(parts) + "."
        g_neg = r["gba_rating"] == "no added benefit"
        f_neg = r["fr_verdict"] in analysis.FR_NEGATIVE
        g_pos = r["gba_rating"] in ("major", "considerable")
        f_pos = r["fr_asmr"] in ("I", "II", "III")
        if g_neg and f_neg:
            sentence += " Germany and France agreed it adds little over existing care."
        elif g_pos and f_pos:
            sentence += " Germany and France both recognised substantial added value."
        elif (g_neg and f_pos) or (g_pos and f_neg):
            sentence += " Germany and France reached opposite verdicts."
        out.append(sentence[0].upper() + sentence[1:])
    else:
        out.append("No German, French or English benefit assessment could be verified yet.")
    return out


def generate_all(all_rows: list[dict], s: dict) -> dict:
    return {r["id"]: bullets(r, all_rows, s) for r in all_rows}
