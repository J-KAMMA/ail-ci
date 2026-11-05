"""The self-hosting file census: `lab/selfhost/files.json` and its report agree.

Checks that `files.json` parses and carries the `ail.selfhost_files/1` schema, that every file
it names still exists, that each result is one of the five recorded outcomes, and that the
totals in `lab/selfhost/FILES.md` equal the counts recomputed from the JSON.  It compiles
nothing: the census JSON is the measurement.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CENSUS = REPO / "lab" / "selfhost" / "files.json"
REPORT = REPO / "lab" / "selfhost" / "FILES.md"
SCHEMA = "ail.selfhost_files/1"
RESULTS = {"typed", "general", "refused", "timeout", "crash"}


def counts(payload):
    files = payload["files"]
    typed = sum(1 for item in files if item["result"] == "typed")
    general = sum(1 for item in files if item["result"] == "general")
    return {
        "files in scope": len(files),
        "built typed": typed,
        "built general": general,
        "refused": sum(1 for item in files if item["result"] == "refused"),
        "timeout": sum(1 for item in files if item["result"] == "timeout"),
        "crash": sum(1 for item in files if item["result"] == "crash"),
        "built total": typed + general,
        "total lines": sum(item["lines"] for item in files),
        "lines in built files": sum(item["lines"] for item in files
                                    if item["result"] in ("typed", "general")),
    }


def report_totals(text):
    rows = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*$", line)
        if match:
            rows[match.group(1)] = int(match.group(2))
    return rows


class SelfhostFileCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(CENSUS.read_text(encoding="utf-8"))
        cls.report = REPORT.read_text(encoding="utf-8")

    def test_schema(self):
        self.assertEqual(self.payload["schema"], SCHEMA)
        self.assertTrue(self.payload.get("base"))
        self.assertTrue(self.payload.get("date"))

    def test_every_named_file_exists(self):
        self.assertTrue(self.payload["files"])
        for record in self.payload["files"]:
            with self.subTest(path=record["path"]):
                self.assertIn(record["result"], RESULTS)
                self.assertIsInstance(record["lines"], int)
                self.assertTrue((REPO / record["path"]).is_file())

    def test_totals_match_report(self):
        rows = report_totals(self.report)
        expected = counts(self.payload)
        for label, value in expected.items():
            with self.subTest(label=label):
                self.assertIn(label, rows, "FILES.md is missing the %r row" % label)
                self.assertEqual(rows[label], value)

    def test_ten_buckets_and_ten_smallest(self):
        refused = [item for item in self.payload["files"] if item["result"] == "refused"]
        self.assertIn("## The 10 largest refusal buckets", self.report)
        self.assertIn("## The 10 smallest refused files", self.report)
        if not refused:
            return
        section = self.report.split("## The 10 largest refusal buckets", 1)[1]
        section = section.split("## The 10 smallest refused files", 1)[0]
        rows = re.findall(r"^\|\s*(\d+)\s*\|", section, re.M)
        self.assertTrue(rows, "FILES.md lists no refusal bucket")
        self.assertLessEqual(len(rows), 10)
        self.assertEqual(int(rows[0]), max(self.payload["totals"]["buckets"].values()))
        smallest = self.report.split("## The 10 smallest refused files", 1)[1]
        listed = re.findall(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|", smallest, re.M)
        self.assertTrue(0 < len(listed) <= 10)
        refused_paths = {item["path"] for item in refused}
        for _lines, path in listed:
            self.assertIn(path, refused_paths)


if __name__ == "__main__":
    unittest.main()
