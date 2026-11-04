"""Merge raw downloads and manual CSVs into the site's data file.

Input:   data/raw/**          (written by fetch_*.py)
         data/manual/*.csv    (maintained by hand)
Output:  data/processed/drugs.json

Every published field is an object, never a bare number:
    {"value": ..., "status": ..., "source_url": ..., "retrieved_date": ..., "notes": ...}
so the site can always show where a number came from. Calculated fields
carry "derived_from" (the fields they were computed from) instead of a URL.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime

from common import MANUAL, PROCESSED, RAW, load_drugs, raw_retrieved_date, read_csv, write_json
from fields import FIELDS, MANUAL_FILES
from taxonomy import company, therapy_area

DRUGS_FDA_PAGE = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={num}"


# ---------------------------------------------------------------------------
# Small helpers to build field objects
# ---------------------------------------------------------------------------
def sourced(value, source_url, retrieved_date, notes="", status="verified"):
    return {"value": value, "status": status, "source_url": source_url,
            "retrieved_date": retrieved_date, "notes": notes}


def missing(status="unknown", notes="", source_url=None, retrieved_date=None):
    return {"value": None, "status": status, "source_url": source_url,
            "retrieved_date": retrieved_date, "notes": notes}


def calculated(value, derived_from, notes=""):
    return {"value": value, "status": "calculated", "derived_from": derived_from, "notes": notes}


def iso_from_ddmmyyyy(text: str):
    """EMA dates look like 18/01/2021."""
    return datetime.strptime(text, "%d/%m/%Y").date().isoformat() if text else None


def iso_from_yyyymmdd(text: str):
    """openFDA dates look like 20191220."""
    return datetime.strptime(text, "%Y%m%d").date().isoformat() if text else None


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def to_number(text: str):
    text = text.replace("$", "").replace(",", "").strip()
    if not text:
        return None
    number = float(text)
    return int(number) if number.is_integer() else number


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_manual() -> dict:
    """Return {(drug_id, field): row} across all manual CSVs."""
    rows = {}
    for filename in MANUAL_FILES:
        path = MANUAL / filename
        if not path.exists():
            continue
        for row in read_csv(path):
            rows[(row["drug_id"].strip(), row["field"].strip())] = {k: (v or "").strip() for k, v in row.items()}
    return rows


def manual_field(manual: dict, drug_id: str, field: str) -> dict:
    """Turn one manual CSV row into a field object (or 'unknown' if absent)."""
    row = manual.get((drug_id, field))
    if row is None:
        return missing(notes="Not yet researched")
    value = row["value"] or None
    kind = FIELDS[field]["kind"]
    if value is not None and kind == "number":
        value = to_number(value)
    return {"value": value, "status": row["status"], "source_url": row["source_url"] or None,
            "retrieved_date": row["retrieved_date"] or None, "notes": row["notes"]}


def load_cms():
    path = RAW / "cms" / "selected_drugs_mfp.csv"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Cite the CMS web page (a stable address) rather than the dated ZIP file,
    # whose URL changes every time CMS publishes an update.
    from fetch_cms import PAGE
    return rows, PAGE, raw_retrieved_date("cms/selected_drugs_mfp.csv")


# ---------------------------------------------------------------------------
# Per-source field builders
# ---------------------------------------------------------------------------
def fda_fields(drug: dict, manual: dict) -> dict:
    app = drug["fda_application"].strip()
    if drug["fda_center"] == "CBER":
        # Cell & gene therapies: not in openFDA, so the date is entered by hand.
        return {
            "fda_approval_date": manual_field(manual, drug["drug_id"], "fda_approval_date"),
            "fda_application": manual_field(manual, drug["drug_id"], "fda_application"),
            "fda_sponsor": missing(notes="CBER product: not in openFDA"),
            "fda_review_priority": missing(notes="CBER product: not in openFDA"),
        }
    raw = json.loads((RAW / "fda" / f"{app}.json").read_text())
    retrieved = raw_retrieved_date(f"fda/{app}.json")
    override = manual.get((drug["drug_id"], "fda_approval_date"))
    page = DRUGS_FDA_PAGE.format(num=app[3:])
    approved = [s for s in raw["original_submissions"] if s["submission_status"] == "AP"]
    if not approved:
        return {"fda_approval_date": missing(notes="No approved original submission in openFDA")}
    orig = approved[0]
    note = "Original application approval date (openFDA Drugs@FDA)"
    out = {
        "fda_approval_date": sourced(iso_from_yyyymmdd(orig["submission_status_date"]), page, retrieved, note),
        "fda_application": sourced(app, page, retrieved),
        "fda_sponsor": sourced(raw["sponsor_name"], page, retrieved),
        "fda_review_priority": sourced((orig.get("review_priority") or "").title() or None, page, retrieved),
    }
    if override:
        # A hand-verified date wins, e.g. Blenrep: openFDA only holds its 2025
        # re-approval, but the FDA first approved it in 2020 (later withdrawn).
        out["fda_approval_date"] = manual_field(manual, drug["drug_id"], "fda_approval_date")
        if manual.get((drug["drug_id"], "fda_application")):
            out["fda_application"] = manual_field(manual, drug["drug_id"], "fda_application")
    return out


def ema_fields(record: dict, retrieved: str) -> dict:
    url = record["medicine_url"]

    def yes_no(key):
        return sourced(record[key].lower() if record[key] else None, url, retrieved)

    opinion = iso_from_ddmmyyyy(record["opinion_adopted_date"])
    ec = iso_from_ddmmyyyy(record["marketing_authorisation_date"])
    if opinion and ec and opinion > ec:
        # The EMA file's opinion field sometimes holds a LATER procedure's opinion
        # (e.g. after a re-authorisation), not the one that led to first approval.
        opinion_field = missing(notes=f"EMA file gives an opinion date ({opinion}) later than the first EC "
                                      "approval, so it cannot be the initial opinion; left blank")
    elif opinion:
        opinion_field = sourced(opinion, url, retrieved)
    else:
        opinion_field = missing(notes="Opinion date is blank in the EMA data file")
    return {
        "ema_opinion_date": opinion_field,
        "ec_approval_date": sourced(iso_from_ddmmyyyy(record["marketing_authorisation_date"]), url, retrieved,
                                    "Initial EU marketing authorisation date"),
        "ema_holder": sourced(record["marketing_authorisation_developer_applicant_holder"], url, retrieved),
        "ema_therapeutic_area": sourced(record["therapeutic_area_mesh"].replace(";", "; "), url, retrieved),
        "atc_code": (sourced(record["atc_code_human"], url, retrieved) if record.get("atc_code_human")
                     else missing(notes="No ATC code assigned in the EMA data file yet")),
        "eu_status": sourced(record["medicine_status"], url, retrieved),
        "eu_orphan": yes_no("orphan_medicine"),
        "eu_conditional": yes_no("conditional_approval"),
        "eu_accelerated": yes_no("accelerated_assessment"),
        "eu_prime": yes_no("prime_priority_medicine"),
        "eu_atmp": yes_no("advanced_therapy"),
    }


def cms_fields(drug: dict, cms_rows, cms_url, cms_retrieved) -> dict:
    brand = drug["brand_us"].upper()
    # CMS names selected drugs like "OZEMPIC; RYBELSUS; WEGOVY".
    matches = [r for r in cms_rows
               if brand in [n.strip() for n in r["Selected Drug Name"].split(";")]]
    if not matches:
        return {"cms_selected": sourced("no", cms_url, cms_retrieved,
                                        "Not in CMS selected drug list (all negotiation cycles to date)")}
    ipay = int(matches[0]["IPAY"])
    # The initial MFP is the price effective from 1 January of the IPAY year
    # (later rows are inflation adjustments).
    initial = [r for r in matches if r["MFP Effective Date"] == f"01/01/{ipay}" and r["Single MFP per 30 DES"]]
    prices = sorted({to_number(r["Single MFP per 30 DES"]) for r in initial})
    note = (f"CMS group: {matches[0]['Selected Drug Name'].title()}. "
            "From the CMS Selected Drug List and MFP data file linked on this page")
    out = {
        "cms_selected": sourced("yes", cms_url, cms_retrieved, note),
        "cms_ipay": sourced(ipay, cms_url, cms_retrieved),
    }
    if len(prices) == 1:
        out["cms_mfp_30day"] = sourced(prices[0], cms_url, cms_retrieved,
                                       f"Initial MFP per 30-day equivalent supply, effective 1 Jan {ipay}. {note}")
    else:
        out["cms_mfp_30day"] = missing(notes="MFP not yet published" if not prices else f"Ambiguous MFPs: {prices}")
    return out


SMR_ORDER = ["important", "moderate", "low", "insufficient"]
ASMR_ORDER = ["I", "II", "III", "IV", "V"]


FR_FIELDS = ("fr_has_date", "fr_has_smr_best", "fr_has_asmr_best", "fr_has_any_insufficient")


def france_fields(drug_id: str, has: dict, retrieved: str) -> dict:
    """HAS first opinion: best SMR and ASMR across indications, and the date."""
    entry = has.get(drug_id) or {}
    op = entry.get("first_opinion")
    if not entry.get("matched_cis"):
        note = "Not listed in the French public medicines database (often: not marketed in France)"
        return {k: missing(notes=note) for k in ("fr_has_date", "fr_has_smr_best", "fr_has_asmr_best", "fr_has_any_insufficient")}
    if not op:
        note = "No HAS inclusion opinion found in the French public medicines database"
        return {k: missing(notes=note) for k in ("fr_has_date", "fr_has_smr_best", "fr_has_asmr_best", "fr_has_any_insufficient")}
    url = op["url"] or "https://base-donnees-publique.medicaments.gouv.fr/"
    note = f"HAS Transparency Committee opinion {op['dossier']} ({op['reason']}). Source: BDPM, Licence ouverte"

    def smr_level(text):
        t = text.lower()
        for fr, en in [("important", "important"), ("modéré", "moderate"), ("modere", "moderate"),
                       ("faible", "low"), ("insuffisant", "insufficient")]:
            if t.startswith(fr):
                return en
        return None

    smrs = [x for x in (smr_level(v) for v in op["smr"]) if x]
    asmrs = [m.group(1) for v in op["asmr"] for m in [re.match(r"(IV|V|III|II|I)\b", v.strip())] if m]
    return {
        "fr_has_date": sourced(op["date"], url, retrieved, note),
        "fr_has_smr_best": (sourced(min(smrs, key=SMR_ORDER.index), url, retrieved, "Best SMR across indications: " + "; ".join(op["smr"]))
                            if smrs else missing(notes="SMR not stated in the opinion record")),
        "fr_has_asmr_best": (sourced(min(asmrs, key=ASMR_ORDER.index), url, retrieved, "Best ASMR across indications: " + "; ".join(op["asmr"]))
                             if asmrs else missing(notes="ASMR not stated in the opinion record")),
        "fr_has_any_insufficient": (sourced("yes" if "insufficient" in smrs else "no", url, retrieved)
                                    if smrs else missing(notes="SMR not stated in the opinion record")),
    }


def calculations(f: dict) -> dict:
    out = {}
    fda, ec = f["fda_approval_date"]["value"], f["ec_approval_date"]["value"]
    if fda and ec:
        lag = days_between(fda, ec)
        out["us_eu_lag_days"] = calculated(lag, ["fda_approval_date", "ec_approval_date"])
        out["first_region"] = calculated("US" if lag > 0 else "EU" if lag < 0 else "Same day",
                                         ["fda_approval_date", "ec_approval_date"])
    it = f["it_gu_date"]
    if ec and it["value"]:
        out["it_access_lag_days"] = calculated(days_between(ec, it["value"]), ["ec_approval_date", "it_gu_date"])
    elif ec and it["status"] == "not_reimbursed_as_of" and it.get("retrieved_date"):
        out["it_days_waiting"] = calculated(
            days_between(ec, it["retrieved_date"]), ["ec_approval_date", "it_gu_date"],
            f"Still not reimbursed when checked on {it['retrieved_date']}")
    gba = f["de_gba_decision_date"]["value"]
    if ec and gba:
        out["de_gba_lag_days"] = calculated(days_between(ec, gba), ["ec_approval_date", "de_gba_decision_date"])
    for field, out_name in [("fr_has_date", "fr_has_lag_days"), ("en_nice_date", "en_nice_lag_days")]:
        value = (f.get(field) or {}).get("value")
        if ec and value:
            out[out_name] = calculated(days_between(ec, value), ["ec_approval_date", field])
    mfp, lst = f.get("cms_mfp_30day", {}).get("value"), f.get("cms_list_price_30day", {}).get("value")
    if mfp and lst:
        out["cms_discount_pct"] = calculated(round((1 - mfp / lst) * 100, 1), ["cms_mfp_30day", "cms_list_price_30day"])
    return out


# ---------------------------------------------------------------------------
def main() -> None:
    drugs = load_drugs()
    manual = load_manual()
    ema = json.loads((RAW / "ema" / "medicines_subset.json").read_text())
    ema_retrieved = raw_retrieved_date("ema/medicines_subset.json")
    cms_rows, cms_url, cms_retrieved = load_cms()
    has = json.loads((RAW / "france" / "has_opinions.json").read_text())
    has_retrieved = raw_retrieved_date("france/has_opinions.json")

    output = []
    for drug in drugs:
        did = drug["drug_id"]
        record = ema[did]
        epar = record["medicine_url"]
        cohort_note = ("Selected by rule: new active substance, first FDA and first EC approval both 2019-2025"
                       if drug["cohort"] == "core" else
                       "Reference only: newer brand of an older molecule, kept for the Medicare comparison; "
                       "excluded from headline statistics")
        f = {
            # Names come from the FDA and EMA records; company and therapy area
            # are assigned by the documented rules in pipeline/taxonomy.py.
            "brand_us": sourced(drug["brand_us"] or None, epar, ema_retrieved),
            "brand_eu": sourced(drug["brand_eu"], epar, ema_retrieved),
            "inn": sourced(drug["inn"], epar, ema_retrieved),
            "company": sourced(company(record["marketing_authorisation_developer_applicant_holder"]), epar,
                               ema_retrieved, "EU marketing authorisation holder, legal form removed"),
            "therapy_area": sourced(therapy_area(record.get("atc_code_human"), record["therapeutic_area_mesh"]),
                                    epar, ema_retrieved, "Assigned from the ATC code (rules in pipeline/taxonomy.py)"),
            "cohort": sourced(drug["cohort"], epar, ema_retrieved, cohort_note),
        }
        f.update(fda_fields(drug, manual))
        f["us_orphan_designated"] = manual_field(manual, did, "us_orphan_designated")
        f.update(ema_fields(record, ema_retrieved))
        for field in ["it_gu_date", "it_reimbursement_class", "de_gba_decision_date",
                      "de_gba_rating_best", "de_gba_any_no_added_benefit", "de_gba_orphan_route"]:
            f[field] = manual_field(manual, did, field)
        f.update(france_fields(did, has, has_retrieved))
        # Researched HAS values fill gaps the automated BDPM files leave; they never override them.
        for field in FR_FIELDS:
            if f[field]["value"] is None and (did, field) in manual:
                f[field] = manual_field(manual, did, field)
        for field in ["en_nice_decision", "en_nice_date", "en_nice_ta"]:
            f[field] = manual_field(manual, did, field)
        f.update(cms_fields(drug, cms_rows, cms_url, cms_retrieved))
        if f["cms_selected"]["value"] == "yes":
            for field in ["cms_list_price_30day", "cms_list_price_year"]:
                f[field] = manual_field(manual, did, field)
        f.update(calculations(f))
        output.append({"drug_id": did, "fields": f})

    dates = [v["retrieved_date"] for d in output for v in d["fields"].values() if v.get("retrieved_date")]
    write_json(PROCESSED / "drugs.json", {
        "schema_version": 1,
        "data_as_of": max(dates),
        "field_definitions": FIELDS,
        "drugs": output,
    })
    print(f"  ok   wrote data/processed/drugs.json ({len(output)} drugs)")


if __name__ == "__main__":
    print("Building processed data ...")
    main()
