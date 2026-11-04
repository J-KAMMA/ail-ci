"""G5a: `import difflib` in compiled programs (bundled stdlib/difflib.py) against CPython's difflib.

The twelve programs in lab/stdlib/difflib/ use get_close_matches, SequenceMatcher, Differ,
unified_diff, context_diff, ndiff, restore and diff_bytes the way ordinary code does.  Ten of
them build with the bundled module and are compared with `python3` on the same source; stdout
and the exit status must agree in the default build and with AIL_UNIFIED_FORCE=1.  Program 04
uses a **kwargs call argument (refused by the general path) and program 12 uses HtmlDiff, which
this module does not publish.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "difflib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

NAMES = [
    "01_close_matches.py", "02_config_typo.py", "03_patch_preview.py",
    "04_unified_edges.py", "05_context_patch.py", "06_ndiff_restore.py",
    "07_differ_junk.py", "08_seq_ratio.py", "09_seq_opcodes.py",
    "10_seq_grouped.py", "11_diff_bytes.py", "12_htmldiff.py",
]
PASSING = [name for name in NAMES if name not in {"04_unified_edges.py", "12_htmldiff.py"}]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibDifflibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-difflib-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual(sorted(p.name for p in PROGRAMS.glob("*.py")), sorted(NAMES + ["bench_ratio.py"]))

    def test_programs_match_cpython(self):
        for name in PASSING:
            source = PROGRAMS / name
            expected = run_cpython(source)
            for label, force in (("default", False), ("unified", True)):
                with self.subTest(program=name, build=label):
                    work = self.dir / (source.stem + "-" + label)
                    work.mkdir(exist_ok=True)
                    program = work / name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(os.environ, AIL_NO_CACHE="1")
                    env.pop("PYTHONPATH", None)
                    if force:
                        env["AIL_UNIFIED_FORCE"] = "1"
                    else:
                        env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                            "--syntax", "python", "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, name)


if __name__ == "__main__":
    unittest.main()
