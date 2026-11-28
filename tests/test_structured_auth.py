"""Regression checks for structured authentication and the combined dataset."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate import ROOT, check


class StructuredAuthValidationTests(unittest.TestCase):
    def setUp(self):
        self.aol = json.loads((ROOT / "providers/aol.json").read_text(encoding="utf-8"))

    def check_record(self, record):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (record["slug"] + ".json")
            path.write_text(json.dumps(record), encoding="utf-8")
            return check(path)

    def test_auth_methods_required_and_closed_enum(self):
        for value in ([], "password", ["unknown"], ["password", "password"], [None], [1]):
            with self.subTest(value=value):
                self.assertTrue(self.check_record({**self.aol, "auth_methods": value}))
        missing = copy.deepcopy(self.aol)
        del missing["auth_methods"]
        self.assertTrue(self.check_record(missing))
        for value in (None, ["password"], ["app-password"], ["oauth2"], ["oauth2", "app-password"]):
            with self.subTest(value=value):
                self.assertEqual(self.check_record({**self.aol, "auth_methods": value}), [])

    def test_auth_methods_requires_evidence(self):
        for changes in ({"authentication": None}, {"authentication": "   "},
                        {"sources": []}, {"client_access": False}):
            with self.subTest(changes=changes):
                self.assertTrue(self.check_record({**self.aol, **changes}))

    def test_combined_dataset_matches_provider_files(self):
        records = [json.loads(path.read_text(encoding="utf-8"))
                   for path in sorted((ROOT / "providers").glob("*.json"))]
        combined = json.loads((ROOT / "dist/email-providers.json").read_text(encoding="utf-8"))
        self.assertEqual(combined["count"], len(records))
        self.assertEqual(sorted(combined["providers"], key=lambda p: p["slug"]),
                         sorted(records, key=lambda p: p["slug"]))


if __name__ == "__main__":
    unittest.main()
