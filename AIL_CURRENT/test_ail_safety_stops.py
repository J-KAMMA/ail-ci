"""Ratchet: the runtime-stop programs that match CPython stay matching.

`lab/safety/stops/RESULTS.md` records the four-mode table.  These programs match in both the default
build and the general (`AIL_UNIFIED_FORCE=1`) build; each must still print the same stdout, exit the
same way, and end stderr with the same line as CPython.  Skipped when no C compiler is available.
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
PROGRAMS = ROOT.parent / "lab" / "safety" / "stops"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MATCHING = (
    "01_zero_floor_text.py",
    "02_zero_mod.py",
    "03_zero_truediv_int.py",
    "05_zero_divmod.py",
    "10_value_int_x.py",
    "11_value_int_empty.py",
    "13_value_chr_neg.py",
    "14_value_sqrt_neg.py",
    "15_value_log_zero.py",
    "19_stop_iteration.py",
    "20_assert_message.py",
)
MODES = ("default", "general")


def last_line(text):
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def environment(general):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    env["AIL_NO_CACHE"] = "1"
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    return env


@unittest.skipUnless(CC, "installed C compiler required")
class SafetyStopsRatchet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-safety-stops-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_matching_programs_stay_matching(self):
        for name in MATCHING:
            source = PROGRAMS / name
            self.assertTrue(source.is_file(), source)
            with self.subTest(program=name):
                work = self.dir / source.stem
                work.mkdir(exist_ok=True)
                copy = work / name
                shutil.copyfile(source, copy)
                expected = subprocess.run([sys.executable, "-B", str(copy)], cwd=str(work),
                                          capture_output=True, text=True, timeout=120,
                                          env=environment(False))
                for mode in MODES:
                    general = mode == "general"
                    out = work / (mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(copy),
                                            "-o", str(out)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=environment(general))
                    self.assertEqual(built.returncode, 0,
                                     "%s %s build failed:\n%s%s"
                                     % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(out)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120,
                                         env=environment(general))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s stdout" % (name, mode))
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit status" % (name, mode))
                    self.assertEqual(last_line(ran.stderr), last_line(expected.stderr),
                                     "%s %s last stderr line" % (name, mode))


if __name__ == "__main__":
    unittest.main()
