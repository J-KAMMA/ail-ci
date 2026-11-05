"""The pyproof census runner on three tiny fixture programs.

The full census (55 programs) is not run here.  A temporary directory holds one
typed, one general and one refused program; report.py writes results.jsonl and
RESULTS.md for them, and this test checks the record fields and the blocker
bucket counts.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT.parent / "lab" / "pyproof" / "report.py"

FIXTURES = {
    "typed.py": 'print("hello")\n',
    "general.py": 'xs = [1, 2, 3]\nprint(list(map(lambda x: x + 1, xs)))\n',
    "refused.py": 'import argparse\nprint(argparse.ArgumentParser)\n',
}


def load_report():
    spec = importlib.util.spec_from_file_location("ail_pyproof_report", str(REPORT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PyproofReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-pyproof-test-")
        cls.dir = Path(cls.temp.name)
        names = []
        for name, text in FIXTURES.items():
            (cls.dir / name).write_text(text)
            names.append(name)
        cls.listfile = cls.dir / "programs.txt"
        cls.listfile.write_text("".join("%s\tnone\n" % (cls.dir / n) for n in names))
        cls.out = cls.dir / "out"
        env = dict(os.environ, AIL_NO_CACHE="1")
        cls.proc = subprocess.run([sys.executable, str(REPORT), "--programs",
                                  str(cls.listfile), "--out", str(cls.out), "-j", "2"],
                                 capture_output=True, text=True, timeout=900, env=env)
        cls.recs = []
        path = cls.out / "results.jsonl"
        if path.is_file():
            cls.recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_runner_exits_cleanly(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-1000:])
        self.assertTrue((self.out / "RESULTS.md").is_file())

    def test_jsonl_fields_and_results(self):
        self.assertEqual(len(self.recs), len(FIXTURES))
        for rec in self.recs:
            for key in ("name", "path", "input", "result", "strict_path",
                        "build_seconds", "python", "base_ref"):
                self.assertIn(key, rec)
            self.assertIn(rec["result"], ("typed", "general", "refused", "wrong"))
        byname = {Path(r["name"]).name: r for r in self.recs}
        self.assertEqual(byname["typed.py"]["result"], "typed")
        self.assertEqual(byname["general.py"]["result"], "general")
        self.assertIn("general path", byname["general.py"].get("first_reason", ""))
        self.assertEqual(byname["refused.py"]["result"], "refused")
        self.assertTrue(byname["refused.py"].get("first_reason"))

    def test_bucket_counts(self):
        module = load_report()
        buckets = module.bucket_counts(self.recs)
        self.assertTrue(buckets)
        self.assertGreaterEqual(sum(b["alone"] for b in buckets.values()), 1)
        self.assertGreaterEqual(sum(b["listed"] for b in buckets.values()), 1)
        for b in buckets.values():
            self.assertGreaterEqual(b["listed"], b["alone"])
            self.assertTrue(b["names"])

    def test_headline_counts(self):
        text = (self.out / "RESULTS.md").read_text()
        self.assertIn("typed 1 / 3, general 1, refused 1, wrong 0", text)

    def test_declared_flags_tolerates_prose_apostrophe(self):
        module = load_report()
        case = self.dir / "flagged.py"
        case.write_text(
            "# ail-build: --exact-int -- the program's masks are wider than int64\n"
            "print(1)\n"
        )
        self.assertEqual(module.declared_flags(case, case), ["--exact-int"])
        case.write_text("# ail-build: --exact-int because it's wide\nprint(1)\n")
        self.assertEqual(module.declared_flags(case, case), ["--exact-int"])
        case.write_text("# ail-build: --exact-int\nprint(1)\n")
        self.assertEqual(module.declared_flags(case, case), ["--exact-int"])

    def test_base_is_named_not_claimed_as_integ(self):
        text = (self.out / "RESULTS.md").read_text()
        base = self.recs[0]["base_ref"]
        self.assertIn("- Base: %s `" % base, text)
        if base not in ("integ", "origin/integ"):
            self.assertNotIn("- Base: integ `", text)


if __name__ == "__main__":
    unittest.main()
