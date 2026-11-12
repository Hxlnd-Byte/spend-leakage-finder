"""Tests that need no AI. Run:  python -m unittest discover tests -v

They prove the date maths, the rules and the scoring are right, using the answer key
as a perfect reader. They do NOT test how well a language model reads PDFs.
"""
import csv
import datetime as dt
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import common as c  # noqa: E402

D = dt.date


class DateMaths(unittest.TestCase):
    def test_add_months_end_of_month(self):
        self.assertEqual(c.add_months(D(2024, 1, 31), 1), D(2024, 2, 29))

    def test_anniversaries(self):
        self.assertEqual(c.anniversaries_passed(D(2023, 9, 1), D(2026, 8, 31)), 2)
        self.assertEqual(c.anniversaries_passed(D(2023, 9, 1), D(2026, 9, 1)), 3)

    def test_allowed_rate_compounds(self):
        self.assertEqual(c.rate_at(100, 4, D(2023, 9, 1), D(2026, 9, 1)), 112.49)
        self.assertEqual(c.rate_at(100, 0, D(2023, 9, 1), D(2026, 9, 1)), 100.0)

    def test_end_date_from_term(self):
        self.assertEqual(c.resolve_end_date(D(2024, 3, 1), 36, None), D(2027, 2, 28))

    def test_auto_renew_rolls_forward(self):
        self.assertEqual(c.current_term_end(D(2026, 8, 31), 12, D(2026, 11, 11)), D(2027, 8, 31))

    def test_notice_deadline_and_status(self):
        dl = c.notice_deadline(D(2027, 2, 28), 90, "days")
        self.assertEqual(dl, D(2026, 11, 30))
        self.assertEqual(c.renewal_status(True, D(2027, 2, 28), dl, D(2026, 11, 11), 90), "ACT_NOW")
        dl2 = c.notice_deadline(D(2027, 1, 31), 90, "days")
        self.assertEqual(c.renewal_status(True, D(2027, 1, 31), dl2, D(2026, 11, 11), 90), "LOCKED_IN")
        self.assertEqual(c.renewal_status(False, D(2027, 1, 31), None, D(2026, 11, 11), 90), "NONE")

    def test_name_matching(self):
        self.assertGreaterEqual(c.name_similarity("AquaPure", "AquaPure Water Systems LLC"), 0.8)
        self.assertLess(c.name_similarity("Karam Office Supplies", "Falcon Security Guarding LLC"), 0.6)


class EndToEndWithPerfectReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for step in (["01_generate_data.py"], ["02_extract.py", "--extractor", "mock"], ["03_reconcile.py"], ["04_score_and_report.py"]):
            r = subprocess.run([sys.executable, *step], cwd=ROOT, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr

    def rows(self, p):
        return list(csv.DictReader(open(p, encoding="utf-8")))

    def test_finds_every_planted_mistake_and_nothing_else(self):
        key = {(r["doc_id"], r["leak_type"]): float(r["overcharge_usd"]) for r in self.rows(ROOT / "data/truth/answer_key.csv")}
        got = {(r["doc_id"], r["leak_type"]): float(r["overcharge_usd"]) for r in self.rows(ROOT / "output/findings.csv")}
        self.assertEqual(set(key), set(got))
        for k in key:
            self.assertAlmostEqual(key[k], got[k], places=2)

    def test_renewals_match_key(self):
        key = {r["contract_id"]: r["status"] for r in self.rows(ROOT / "data/truth/renewal_key.csv")}
        self.assertEqual(sorted(key.values()).count("ACT_NOW"), 6)
        self.assertEqual(sorted(key.values()).count("LOCKED_IN"), 5)


if __name__ == "__main__":
    unittest.main()
