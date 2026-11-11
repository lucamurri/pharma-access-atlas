"""Tests proving the validator catches each kind of bad data.

Run:  python3 -m unittest discover pipeline
Each test copies the real data into a temporary folder, breaks one rule,
and checks that validate.py reports it.
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import common
import validate


class ValidatorCatchesBadData(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(common.MANUAL, self.tmp / "manual")
        shutil.copytree(common.PROCESSED, self.tmp / "processed")
        # Point the validator (and the drug-list loader) at the copies.
        validate.MANUAL = self.tmp / "manual"
        validate.PROCESSED = self.tmp / "processed"
        self._load_drugs = validate.load_drugs
        validate.load_drugs = lambda: common.read_csv(self.tmp / "manual" / "drugs.csv")
        validate.errors.clear()
        validate.warnings.clear()
        self.data = json.loads((self.tmp / "processed" / "drugs.json").read_text())

    def tearDown(self):
        validate.MANUAL, validate.PROCESSED = common.MANUAL, common.PROCESSED
        validate.load_drugs = self._load_drugs
        shutil.rmtree(self.tmp)

    def run_validator(self) -> str:
        (self.tmp / "processed" / "drugs.json").write_text(json.dumps(self.data))
        validate.main()
        return "\n".join(validate.errors)

    def field(self, drug_id, name):
        drug = next(d for d in self.data["drugs"] if d["drug_id"] == drug_id)
        return drug["fields"][name]

    def test_real_data_passes(self):
        self.assertEqual(self.run_validator(), "")

    def test_value_without_source_fails(self):
        self.field("enhertu", "ec_approval_date")["source_url"] = None
        self.assertIn("no valid source_url", self.run_validator())

    def test_value_without_retrieved_date_fails(self):
        self.field("enhertu", "ec_approval_date")["retrieved_date"] = ""
        self.assertIn("no valid retrieved_date", self.run_validator())

    def test_access_before_approval_fails(self):
        f = self.field("enhertu", "it_gu_date")
        f.update(value="2020-01-01", status="verified", source_url="https://example.org", retrieved_date="2026-01-01")
        self.assertIn("before EC approval", self.run_validator())

    def test_opinion_after_approval_fails(self):
        self.field("enhertu", "ema_opinion_date")["value"] = "2030-01-01"
        self.assertIn("after EC approval", self.run_validator())

    def test_price_opinion_after_publication_fails(self):
        f = self.field("enhertu", "it_price_opinion_date")
        f.update(value="2023-08-01", status="verified", source_url="https://example.org", retrieved_date="2026-01-01")
        self.assertIn("AIFA price opinion (2023-08-01) is after", self.run_validator())

    def test_bad_innovativeness_fails(self):
        f = self.field("enhertu", "it_innovative")
        f.update(value="partial", status="verified", source_url="https://example.org", retrieved_date="2026-01-01")
        self.assertIn("it_innovative", self.run_validator())

    def test_bad_rating_fails(self):
        f = self.field("enhertu", "de_gba_rating_best")
        f.update(value="fantastic", status="verified", source_url="https://example.org", retrieved_date="2026-01-01")
        self.assertIn("must be one of", self.run_validator())

    def test_duplicate_drug_fails(self):
        path = self.tmp / "manual" / "drugs.csv"
        rows = common.read_csv(path)
        with open(path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=list(rows[0].keys())).writerow(rows[0])
        self.assertIn("duplicate drug_id", self.run_validator())

    def test_duplicate_manual_row_fails(self):
        path = self.tmp / "manual" / "cms_list_prices.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines + [lines[1]]) + "\n")
        self.assertIn("duplicate rows", self.run_validator())


if __name__ == "__main__":
    unittest.main()
