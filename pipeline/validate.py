"""Quality gate: fail the build if the data breaks any credibility rule.

Checks
  1. Manual CSVs: correct header, known drug_id and field, valid status,
     no duplicate (drug_id, field) rows, fields in the right file.
  2. Sourcing: every non-null value has a source_url (http/https) and a
     valid retrieved_date that isn't in the future. Calculated values must
     say what they were derived from.
  3. Status consistency: 'verified' needs a value; 'unknown' must not have one.
  4. Allowed values: yes/no fields, G-BA ratings, Italian classes, ISO dates.
  5. Logical dates: CHMP opinion <= EC approval; Italian reimbursement and
     G-BA decision on or after EC approval; AIFA price opinion <= Board
     resolution <= GU publication; nothing dated in the future;
     FDA and EC approvals inside the 2019-2025 study window.
  6. Duplicates: drug_id, brands, FDA application and EMA number are unique.

Run:  python3 pipeline/validate.py      (exit code 1 = errors found)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date

from common import MANUAL, MANUAL_HEADER, MANUAL_STATUSES, PROCESSED, load_drugs, read_csv
from fields import FIELDS, MANUAL_FILES

WINDOW = ("2019-01-01", "2025-12-31")
TODAY = date.today().isoformat()

errors: list[str] = []
warnings: list[str] = []


def is_iso_date(text) -> bool:
    try:
        date.fromisoformat(text)
        return len(text) == 10
    except (TypeError, ValueError):
        return False


def check_manual_csvs(drug_ids: set) -> None:
    for filename, allowed_fields in MANUAL_FILES.items():
        path = MANUAL / filename
        if not path.exists():
            errors.append(f"{filename}: file missing")
            continue
        rows = read_csv(path)
        with open(path, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != MANUAL_HEADER:
            errors.append(f"{filename}: header must be {','.join(MANUAL_HEADER)}")
        seen = Counter()
        for i, row in enumerate(rows, start=2):  # line 1 is the header
            where = f"{filename} line {i}"
            did, field, status = row["drug_id"].strip(), row["field"].strip(), row["status"].strip()
            seen[(did, field)] += 1
            if did not in drug_ids:
                errors.append(f"{where}: unknown drug_id '{did}'")
            if field not in allowed_fields:
                errors.append(f"{where}: field '{field}' does not belong in {filename}")
            if status not in MANUAL_STATUSES:
                errors.append(f"{where}: status '{status}' must be one of {sorted(MANUAL_STATUSES)}")
            if status != "unknown" and not row["source_url"].strip():
                errors.append(f"{where}: status '{status}' needs a source_url")
        for (did, field), n in seen.items():
            if n > 1:
                errors.append(f"{filename}: duplicate rows for {did} / {field}")


def check_field(drug_id: str, name: str, obj: dict) -> None:
    where = f"{drug_id}.{name}"
    meta = FIELDS.get(name)
    if meta is None:
        errors.append(f"{where}: field not in the data dictionary (pipeline/fields.py)")
        return
    value, status = obj.get("value"), obj.get("status")

    # --- sourcing ------------------------------------------------------
    if status == "calculated":
        if not obj.get("derived_from"):
            errors.append(f"{where}: calculated value without 'derived_from'")
    elif value is not None or status in ("not_reimbursed_as_of", "not_assessed"):
        url, retrieved = obj.get("source_url") or "", obj.get("retrieved_date")
        if not url.startswith(("http://", "https://")):
            errors.append(f"{where}: value '{value}' has no valid source_url")
        if not is_iso_date(retrieved):
            errors.append(f"{where}: value '{value}' has no valid retrieved_date")
        elif retrieved > TODAY:
            errors.append(f"{where}: retrieved_date {retrieved} is in the future")

    # --- status consistency ----------------------------------------------
    if status == "verified" and value is None:
        errors.append(f"{where}: status 'verified' but value is empty")
    if status == "unknown" and value is not None:
        errors.append(f"{where}: status 'unknown' but a value is filled in")
    if status == "unknown":
        warnings.append(f"{where}: unknown ({obj.get('notes') or 'no note'})")

    # --- allowed values ----------------------------------------------------
    if value is None:
        return
    kind = meta["kind"]
    if kind == "date" and not is_iso_date(value):
        errors.append(f"{where}: '{value}' is not a YYYY-MM-DD date")
    elif kind == "date" and value > TODAY:
        errors.append(f"{where}: date {value} is in the future")
    if kind == "yes_no" and value not in ("yes", "no"):
        errors.append(f"{where}: '{value}' must be yes or no")
    if kind == "enum" and value not in meta["allowed"]:
        errors.append(f"{where}: '{value}' must be one of {meta['allowed']}")
    if kind == "number" and not isinstance(value, (int, float)):
        errors.append(f"{where}: '{value}' must be a number")


def check_dates(drug_id: str, f: dict) -> None:
    def v(name):
        return (f.get(name) or {}).get("value")

    fda, opinion, ec = v("fda_approval_date"), v("ema_opinion_date"), v("ec_approval_date")
    if opinion and ec and opinion > ec:
        errors.append(f"{drug_id}: CHMP opinion ({opinion}) is after EC approval ({ec})")
    for name, label in [("it_gu_date", "Italian reimbursement"), ("de_gba_decision_date", "G-BA decision")]:
        if ec and v(name) and v(name) < ec:
            errors.append(f"{drug_id}: {label} ({v(name)}) is before EC approval ({ec})")
    # Italian procedure: price opinion, then Board resolution, then publication.
    steps = [("it_price_opinion_date", "AIFA price opinion"), ("it_board_date", "AIFA Board resolution"),
             ("it_gu_date", "Italian reimbursement")]
    for (a, la), (b, lb) in zip(steps, steps[1:]):
        if v(a) and v(b) and v(a) > v(b):
            errors.append(f"{drug_id}: {la} ({v(a)}) is after {lb} ({v(b)})")
    # The scientific committee can meet again after the price opinion (e.g. Zolgensma), so no order is enforced there.
    for name, value in [("fda_approval_date", fda), ("ec_approval_date", ec)]:
        if value and not (WINDOW[0] <= value <= WINDOW[1]):
            errors.append(f"{drug_id}: {name} {value} is outside the {WINDOW[0]}..{WINDOW[1]} study window")
    if not fda:
        errors.append(f"{drug_id}: FDA approval date is missing (required for inclusion)")
    if not ec:
        errors.append(f"{drug_id}: EC approval date is missing (required for inclusion)")


def check_duplicates(drugs: list[dict]) -> None:
    for column in ["drug_id", "brand_us", "brand_eu", "ema_product_number", "fda_application"]:
        values = [d[column].strip().lower() for d in drugs if d[column].strip()]
        for value, n in Counter(values).items():
            if n > 1:
                errors.append(f"drugs.csv: duplicate {column} '{value}'")


def main() -> int:
    drugs = load_drugs()
    check_duplicates(drugs)
    check_manual_csvs({d["drug_id"] for d in drugs})

    processed = json.loads((PROCESSED / "drugs.json").read_text())
    ids = [d["drug_id"] for d in processed["drugs"]]
    if len(ids) != len(set(ids)):
        errors.append("drugs.json: duplicated drug_id")
    for d in processed["drugs"]:
        for name, obj in d["fields"].items():
            check_field(d["drug_id"], name, obj)
        check_dates(d["drug_id"], d["fields"])

    print(f"Validation: {len(errors)} error(s), {len(warnings)} warning(s)")
    for w in warnings:
        print("  warn ", w)
    for e in errors:
        print("  ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
