"""shport0: lab/selfhost/port_order.json and selfhost/CORPUS.txt are well formed.

The JSON parses with the ail.selfhost_port_order/1 schema, ranks at least 10 modules with every
column, and every ranked module's file exists.  CORPUS.txt holds 376 sorted, unique
``sha256  path`` lines whose files exist.  The hashes freeze the corpus: a mismatch is printed,
and fails the test only with AIL_SELFHOST_CORPUS_STRICT=1, so that an ordinary compiler edit does
not turn this test red (re-freeze with ``python3 tools/selfhost_port_order.py --corpus``).
"""
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
COLUMNS = ("lines", "layer", "cycle", "own_s", "own_share", "build", "first_refusal",
           "ast_uses", "environ_reads", "hot")


class PortOrderTest(unittest.TestCase):
    def test_port_order_json(self):
        data = json.loads((REPO / "lab" / "selfhost" / "port_order.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "ail.selfhost_port_order/1")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", data["base_commit"]))
        ranked = data["ranked"]
        self.assertGreaterEqual(len(ranked), 10)
        for k, row in enumerate(ranked):
            self.assertEqual(row["rank"], k + 1)
            for c in COLUMNS:
                self.assertIn(c, row, (row["module"], c))
            self.assertLessEqual(row["lines"], 1500)
            self.assertTrue((REPO / row["path"]).exists(), row["path"])
        later = {row["module"] for row in data["later"]}
        self.assertEqual(later, {"pyfunc", "cruntime", "pyboxed2", "ail_chatgpt"})
        self.assertFalse(later & {row["module"] for row in ranked})

    def test_corpus(self):
        lines = (REPO / "selfhost" / "CORPUS.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 376)
        paths = []
        bad = []
        for line in lines:
            digest, path = line.split("  ", 1)
            self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", digest), line)
            p = REPO / path
            self.assertTrue(p.exists(), path)
            if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                bad.append(path)
            paths.append(path)
        self.assertEqual(paths, sorted(set(paths)))
        if bad:
            print("CORPUS.txt: %d of 376 files changed since the freeze, first %s" % (len(bad), bad[0]))
        if os.environ.get("AIL_SELFHOST_CORPUS_STRICT") == "1":
            self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
