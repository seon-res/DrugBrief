import importlib.util
from datetime import date
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("fetch_data", Path(__file__).resolve().parents[1] / "scripts" / "fetch_data.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class TestNormalize(unittest.TestCase):
    def test_original_approved_and_date_filtering(self):
        row = {
            "application_number": "NDA123456", "sponsor_name": "Example Co",
            "products": [{"brand_name": "Brand X"}],
            "submissions": [
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20261001"},
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20260403"},
            ]
        }
        data = mod.normalize_fda_application(row, date(2026, 1, 1), date(2026, 10, 15))
        self.assertEqual(data["date"], "2026-04-03")
        self.assertIn("ApplNo=123456", data["url"])

    def test_cross_matched_submissions_rejected(self):
        row = {
            "application_number": "NDA123456",
            "submissions": [
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20261001"},
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20030101"}
            ]
        }
        self.assertIsNone(mod.normalize_fda_application(row, date(2025, 10, 15), date(2026, 10, 15)))

    def test_trial_requires_drug_and_phase(self):
        base = {"protocolSection": {
            "identificationModule": {"nctId": "NCT01234567", "briefTitle": "Example Trial"},
            "statusModule": {"lastUpdatePostDateStruct": {"date": "2026-10-12"}, "overallStatus": "RECRUITING"},
            "designModule": {"phases": ["PHASE2"]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Drug X"}]}
        }}
        self.assertEqual(mod.normalize_trial(base)["id"], "NCT01234567")
        base["protocolSection"]["armsInterventionsModule"]["interventions"][0]["type"] = "DEVICE"
        self.assertIsNone(mod.normalize_trial(base))


if __name__ == "__main__":
    unittest.main()
