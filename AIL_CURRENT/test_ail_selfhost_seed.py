"""The C-seed estimate: corpus shape and the numbers in lab/selfhost/SEED.md.

`tools/selfhost_seed_estimate.py --report-only` fits the committed corpus JSON and prints the
low/mid/high estimates; it builds nothing.  The same numbers, written into SEED.md as a machine
readable comment, must equal them exactly.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "selfhost_seed_estimate.py"
CORPUS = ROOT / "lab" / "selfhost" / "seed_corpus.json"
SEED = ROOT / "lab" / "selfhost" / "SEED.md"
ESTIMATES = re.compile(r"<!-- estimates: (\{.*\}) -->")


class SelfhostSeedEstimate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = json.loads(CORPUS.read_text(encoding="utf-8"))

    def test_corpus_shape(self):
        self.assertEqual(self.corpus.get("schema"), "ail.selfhost_seed/1")
        self.assertGreaterEqual(len(self.corpus["rows"]), 40)
        modes = {record["mode"] for record in self.corpus["fixed"]}
        self.assertEqual(modes, {"typed", "general"})
        for record in self.corpus["rows"] + self.corpus["fixed"]:
            for key in ("lines", "ast_nodes", "c_bytes", "c_gzip_bytes", "binary_bytes", "mode"):
                self.assertIn(key, record)
            self.assertGreater(record["c_bytes"], 0)
            self.assertGreater(record["binary_bytes"], 0)
        compiler = self.corpus.get("compiler")
        self.assertIsNotNone(compiler, "the corpus records no compiler stats")
        for key in ("files", "lines", "ast_nodes", "top_functions", "top_classes"):
            self.assertIsInstance(compiler[key], int)
        self.assertGreater(compiler["files"], 0)
        self.assertGreater(compiler["ast_nodes"], 0)

    def test_seed_md_matches_tool(self):
        done = subprocess.run(
            [sys.executable, "-B", str(TOOL), "--report-only", "--corpus", str(CORPUS)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr)
        computed = json.loads(done.stdout)
        found = ESTIMATES.search(SEED.read_text(encoding="utf-8"))
        self.assertIsNotNone(found, "SEED.md has no '<!-- estimates: {...} -->' line")
        self.assertEqual(json.loads(found.group(1)), computed)
        for key in ("c_bytes", "gzip_bytes", "binary_bytes"):
            self.assertEqual(set(computed[key]), {"low", "mid", "high"})
            self.assertLessEqual(computed[key]["low"], computed[key]["mid"])
            self.assertLessEqual(computed[key]["mid"], computed[key]["high"])


if __name__ == "__main__":
    unittest.main()
