"""Ratchet: the type-mixing programs that match CPython stay matching.

`lab/safety/typemix/RESULTS.md` records the four-mode table.  These programs match in both the
default build and the general (`AIL_UNIFIED_FORCE=1`) build; each must still print the same stdout,
exit the same way, and end stderr with the same line as CPython.  Skipped when no C compiler is
available.
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
PROGRAMS = ROOT.parent / "lab" / "safety" / "typemix"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MATCHING = (
    "t01_bool_add.py",
    "t02_bool_sum.py",
    "t03_bool_mul.py",
    "t04_bool_index.py",
    "t05_bool_abs.py",
    "t06_bool_format.py",
    "t07_bool_div.py",
    "t08_bool_max.py",
    "t09_bool_isinstance.py",
    "t10_bool_arith_mix.py",
    "t11_dict_bool_key.py",
    "t12_set_zero.py",
    "t13_hash_neg.py",
    "t14_dict_numeric_keys.py",
    "t15_big_int_float_eq.py",
    "t16_big_int_float_lt.py",
    "t18_floor_neg_float.py",
    "t19_mod_neg_float.py",
    "t20_divmod_mixed.py",
    "t21_round_half.py",
    "t22_nan_eq.py",
    "t23_sorted_mixed.py",
    "t25_float_int_convert.py",
    "t26_str_add_int.py",
    "t27_str_mul_bool.py",
    "t28_str_lt_int.py",
    "t29_int_str_float.py",
    "t30_float_str_underscore.py",
    "t31_str_float_repr.py",
    "t32_repr_neg_zero.py",
    "t33_percent_format.py",
    "t34_str_int_eq.py",
    "t35_none_add.py",
    "t36_none_lt.py",
    "t37_none_index.py",
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
class SafetyTypemixRatchet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-safety-typemix-test-")
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
