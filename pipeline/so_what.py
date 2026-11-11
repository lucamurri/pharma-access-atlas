"""Three 'so what' bullets per drug brief, generated from the data, in each site language.

With ~200 drugs the bullets are written by rules instead of by hand, so every sentence is grounded in the
drug's own sourced values and in medians for the whole atlas. The wording is descriptive ("longer than the
median", never a rank among drugs) and never adds facts that are not in the data. The sentence patterns live in site/i18n/<lang>.json
(keys "so.*"); check_text.py verifies every number in the English version.
"""
from __future__ import annotations

import analysis
import i18n


def bullets(r: dict, all_rows: list[dict], s: dict, t: i18n.Strings) -> list[str]:
    core = analysis.core(all_rows)
    out = []

    # 1. Regulatory timing ----------------------------------------------------
    lag, med = r["lag"], analysis.days(s["lag_median"])
    if lag is None:
        out.append(t("so.lag_na"))
    elif lag > 0:
        cmp = t("so.cmp_longer") if lag > med else t("so.cmp_shorter") if lag < med else t("so.cmp_same")
        out.append(t("so.lag_after", lag=t.num(lag), cmp=cmp, med=t.num(med)))
    elif lag < 0:
        out.append(t("so.lag_eu_first", lag=t.num(-lag), n=t.num(s["lag_eu_first"])))
    else:
        out.append(t("so.lag_same_day"))

    # 2. Italian access (the median counts drugs still waiting) -----------------
    it_med = s["access"]["it"]["median"]
    if r["it_lag"] is not None:
        # Compared with the median only: no rank among drugs, which would read as a league table.
        cmp = (t("so.cmp_longer") if r["it_lag"] > it_med else t("so.cmp_shorter") if r["it_lag"] < it_med
               else t("so.cmp_equal"))
        out.append(t("so.it_reimbursed", cls=r["it_class"], lag=t.num(r["it_lag"]), cmp=cmp, med=t.num(it_med)))
    elif r["it_status"] == "not reimbursed":
        out.append(t("so.it_waiting", days=t.num(r["it_waiting"]), cls=r["it_class"], date=t.date(r["it_checked"])))
    else:
        out.append(t("so.it_unknown"))

    # 3. Value verdicts across Germany, France and England -----------------------
    parts = []
    if r["gba_rating"] in analysis.G_BA_ORDER:
        parts.append(t("so.de_found", rating=t("so.rating." + r["gba_rating"]))
                     + (t("so.de_orphan") if r["gba_orphan"] == "yes" else ""))
    elif r["gba_rating"] == "not assessed":
        parts.append(t("so.de_none"))
    if r["fr_asmr"]:
        parts.append(t("so.fr_rated", asmr=t("so.asmr." + r["fr_asmr"])))
    elif r["fr_verdict"] == "SMR insufficient":
        parts.append(t("so.fr_insufficient"))
    if r["en_decision"]:
        parts.append(t("so.en", decision=t("so.nice." + r["en_decision"])))
    if parts:
        sentence = t("so.join").join(parts) + t("so.end")
        g_neg = r["gba_rating"] == "no added benefit"
        f_neg = r["fr_verdict"] in analysis.FR_NEGATIVE
        g_pos = r["gba_rating"] in ("major", "considerable")
        f_pos = r["fr_asmr"] in ("I", "II", "III")
        if g_neg and f_neg:
            sentence += " " + t("so.agree_neg")
        elif g_pos and f_pos:
            sentence += " " + t("so.agree_pos")
        elif (g_neg and f_pos) or (g_pos and f_neg):
            sentence += " " + t("so.opposite")
        out.append(sentence[0].upper() + sentence[1:])
    else:
        out.append(t("so.no_verdicts"))
    return out


def generate_all(all_rows: list[dict], s: dict, lang: str = "en") -> dict:
    t = i18n.Strings(lang)
    return {r["id"]: bullets(r, all_rows, s, t) for r in all_rows}
