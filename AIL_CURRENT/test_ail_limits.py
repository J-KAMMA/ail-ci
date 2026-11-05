"""L1: every entry in docs/LIMITATIONS.md is backed by a probe in lab/limits/.

The page describes what an AIL 0.1 user meets first.  Each section names one program in
lab/limits/; lab/limits/expected.json records what the default build currently does with it: either
the first refusal line, or "builds, and the program prints this".  This module re-runs every probe,
so a limitation that is lifted (or a refusal that changes) fails here instead of leaving the page
wrong.  It skips when there is no C compiler, like the other build tests.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
LIMITS = ROOT.parent / "lab" / "limits"
DOC = ROOT.parent / "docs" / "LIMITATIONS.md"
EXPECTED = LIMITS / "expected.json"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PROBE_RE = re.compile(r"lab/limits/([0-9]{2}_[a-z0-9_]+\.py)")
LOCATION_RE = re.compile(r"^[^\s:]+:\d+:\d+: ")
LIFTED = "limitation lifted: update docs/LIMITATIONS.md and lab/limits/expected.json"


def strip_location(text):
    return "\n".join(LOCATION_RE.sub("", line) for line in text.splitlines())


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class LimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-limits-test-")
        cls.dir = Path(cls.temp.name)
        cls.entries = json.loads(EXPECTED.read_text(encoding="utf-8"))["probes"]
        cls.sources = sorted(LIMITS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fifteen_probes_recorded(self):
        self.assertEqual(len(self.sources), 15, [p.name for p in self.sources])
        self.assertEqual(len(self.entries), 15, [e["probe"] for e in self.entries])
        self.assertEqual(sorted(e["probe"] for e in self.entries),
                         [p.name for p in self.sources])

    def test_doc_section_per_probe(self):
        doc = DOC.read_text(encoding="utf-8")
        sections = re.split(r"^### ", doc, flags=re.M)[1:]
        self.assertEqual(len(sections), 15, "docs/LIMITATIONS.md must have 15 entries")
        named = []
        for section in sections:
            title = section.splitlines()[0].strip()
            found = PROBE_RE.findall(section)
            self.assertEqual(len(found), 1,
                             "%r must name exactly one lab/limits/ probe" % title)
            self.assertTrue((LIMITS / found[0]).is_file(),
                            "%r names missing lab/limits/%s" % (title, found[0]))
            named.append(found[0])
        self.assertEqual(sorted(named), [p.name for p in self.sources])
        for entry in self.entries:
            self.assertIn("lab/limits/" + entry["probe"], doc,
                          "%s is recorded but not in docs/LIMITATIONS.md" % entry["probe"])

    def test_probes_still_behave_as_recorded(self):
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        env.pop("AIL_UNIFIED_FORCE", None)
        for entry in self.entries:
            with self.subTest(probe=entry["probe"]):
                work = self.dir / Path(entry["probe"]).stem
                work.mkdir(exist_ok=True)
                program = work / entry["probe"]
                shutil.copyfile(LIMITS / entry["probe"], program)
                exe = work / "probe.out"
                built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                        "--syntax", "python", "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                build_text = strip_location(built.stdout + built.stderr)
                expected = run_cpython(program)
                if entry["expect"] == "refused":
                    self.assertNotEqual(built.returncode, 0,
                                        "%s\n%s\n%s" % (LIFTED, entry["probe"], build_text))
                    self.assertIn(entry["text"], build_text,
                                  "%s (refusal text changed)\n%s" % (LIFTED, build_text))
                    self.assertEqual(entry["cpython"], expected.stdout.strip(),
                                     "the recorded CPython output no longer matches")
                    continue
                self.assertEqual(built.returncode, 0,
                                 "probe is now refused: %s\n%s"
                                 % (LIFTED, build_text))
                if entry.get("text"):
                    self.assertIn(entry["text"], build_text,
                                  "%s (build note changed)\n%s" % (LIFTED, build_text))
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                if entry.get("stderr"):
                    self.assertIn(entry["stderr"],
                                  strip_location(ran.stdout + ran.stderr), entry["probe"])
                self.assertEqual(ran.stdout, entry["stdout"], entry["probe"])
                self.assertEqual(ran.returncode, entry["exit"], entry["probe"])
                self.assertEqual(entry["cpython"], expected.stdout, entry["probe"])


if __name__ == "__main__":
    unittest.main()
