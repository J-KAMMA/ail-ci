"""Ratchet: the iteration-mutation programs that match CPython stay matching.

`lab/safety/itermut/RESULTS.md` records the four-mode table.  These programs match in both the
default build and the general (`AIL_UNIFIED_FORCE=1`) build; each must still print the same stdout,
exit the same way, and end stderr with the same line as CPython.  Skipped when no C compiler is
available.  The programs with a silent-wrong cell in RESULTS.md (18, 25, 26, 27) are deliberately
absent: this module records no wrong result as acceptable.
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
PROGRAMS = ROOT.parent / "lab" / "safety" / "itermut"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MATCHING = (
    "01_list_append_bounded.py",
    "02_list_remove_current.py",
    "03_list_pop0.py",
    "04_list_insert0.py",
    "05_list_del_index.py",
    "06_list_clear.py",
    "07_list_slice_clear.py",
    "08_list_sort_midloop.py",
    "09_list_reverse_midloop.py",
    "10_list_extend_self.py",
    "11_list_enumerate.py",
    "12_list_zip.py",
    "13_list_reversed.py",
    "14_list_saved_iter.py",
    "15_list_comprehension.py",
    "16_list_genexp.py",
    "17_sorted_key_appends.py",
    "19_dict_add_key.py",
    "20_dict_delete_key.py",
    "21_dict_value_only.py",
    "22_dict_items_add.py",
    "23_dict_keys_add.py",
    "24_dict_values_add.py",
    "28_big_list_append.py",
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
class SafetyIterMutRatchet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-safety-itermut-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_matching_programs_stay_matching(self):
        self.assertGreaterEqual(len(MATCHING), 24)
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
