"""Ratchet for generated-C determinism (lab/selfhost/DETERMINISM.md).

Builds three small programs twice each, with PYTHONHASHSEED=0 and PYTHONHASHSEED=1 in different
working and output directories, and compares the generated `program.c` byte for byte.  Only the
programs that `lab/selfhost/DETERMINISM.md` lists as identical under the general build are
asserted: a program with a recorded difference class is not asserted, so this test never fails on
known nondeterminism.  When a difference is fixed, add the row to the document and the ratchet
tightens automatically.

Skips without a C compiler (the compiler needs one to link `program.c`).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / "ail_chatgpt.py")
DOC = REPO / "lab" / "selfhost" / "DETERMINISM.md"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PROGRAMS = (
    ("stdlib/bisect/alias_import.py", "lab/stdlib/bisect/alias_import.py"),
    ("examples/tutorial_project/step1.py", "examples/tutorial_project/step1.py"),
    ("compare/berth_sim", "lab/compare/src/berth_sim/main.py"),
)


def listed_identical():
    """(program, mode) rows the document calls identical; empty when it is absent."""
    if not DOC.is_file():
        return set()
    rows = set()
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[1] in ("identical", "refused"):
            if cells[1] == "identical":
                rows.add((cells[0].strip("`"), "general"))
            if cells[2] == "identical":
                rows.add((cells[0].strip("`"), "typed"))
    return rows


def build(source, work, seed):
    work.mkdir(parents=True, exist_ok=True)
    program = work / source.name
    shutil.copyfile(source, program)
    env = {k: v for k, v in os.environ.items()
           if k not in ("AIL_CACHE", "AIL_NO_CACHE", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
                        "PYTHONHASHSEED")}
    env.update(AIL_NO_CACHE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONHASHSEED=str(seed))
    done = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                           "-o", str(work / "prog"), "--debug-dir", str(work / "debug")],
                          cwd=str(work), env=env, capture_output=True, text=True, timeout=600)
    program_c = work / "debug" / "program.c"
    return done, program_c


@unittest.skipUnless(CC, "installed C compiler required")
class DeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = listed_identical()
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-cdet-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_document_lists_at_least_one_identical_program(self):
        self.assertTrue(self.rows, "lab/selfhost/DETERMINISM.md lists no identical program")

    def test_listed_programs_are_stable_across_hash_seeds(self):
        checked = 0
        for name, relative in PROGRAMS:
            if (name, "general") not in self.rows:
                continue
            source = REPO / relative
            first, first_c = build(source, self.dir / name.replace("/", "_") / "s0", 0)
            second, second_c = build(source, self.dir / name.replace("/", "_") / "s1", 1)
            with self.subTest(program=name):
                self.assertEqual(first.returncode, 0, first.stderr[-2000:])
                self.assertEqual(second.returncode, 0, second.stderr[-2000:])
                self.assertTrue(first_c.is_file(), "no program.c from seed 0")
                self.assertTrue(second_c.is_file(), "no program.c from seed 1")
                self.assertEqual(first_c.read_bytes(), second_c.read_bytes(),
                                 "program.c differs between PYTHONHASHSEED=0 and 1")
                checked += 1
        self.assertTrue(checked, "none of the sampled programs is listed as identical")


if __name__ == "__main__":
    unittest.main()
