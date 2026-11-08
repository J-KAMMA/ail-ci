"""stdfall2: `copy`, `timeit` and `marshal` in compiled programs (bundled stdlib).

The eighteen programs under lab/stdlib/{copy,timeit,marshal}/ exercise the
bundled AIL source modules `AIL_CURRENT/stdlib/copy.py`, `timeit.py` and
`marshal.py` against CPython 3.12.  Every passing program is compiled with the
default command and with AIL_UNIFIED_FORCE=1 and run beside `python3` on the
same source; stdout and the exit status must agree.

Three of the eighteen are recorded as follow-ups in
lab/stdlib/stdfall2/RESULTS.md instead of compared:

* copy/03_user_class_hooks.py builds but differs: `__copy__`/`__deepcopy__`
  are not dispatched (the compiler refuses the dunder call on an unknown
  static kind), so the class is copied through its `__dict__`.
* timeit/06_string_stmt.py builds but stops at run time with
  `TypeError: timeit.Timer: a string stmt needs exec, which is not built`.
* marshal/02_big_ints.py cannot build: `2**70` is `int64 constant out of
  range` in the default build.
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
LAB = ROOT.parent / "lab" / "stdlib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "copy/01_nested_lists_dicts.py",
    "copy/02_tuples_sets.py",
    "copy/04_user_class_plain.py",
    "copy/05_recursive_list.py",
    "copy/06_shared_subobjects.py",
    "timeit/01_default_timer.py",
    "timeit/02_timer_timeit.py",
    "timeit/03_timer_repeat.py",
    "timeit/04_module_timeit.py",
    "timeit/05_setup_and_custom_timer.py",
    "marshal/01_ints_bool_none.py",
    "marshal/03_floats.py",
    "marshal/04_strings_bytes.py",
    "marshal/05_lists_tuples.py",
    "marshal/06_dicts.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibStdfall2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-stdfall2-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(LAB.glob("copy/*.py")) + sorted(LAB.glob("timeit/*.py")) + \
            sorted(LAB.glob("marshal/*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual(len(self.sources), 18)
        self.assertEqual(len(PASSING), 15)
        for name in PASSING:
            self.assertTrue((LAB / name).is_file(), name)

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for name in PASSING:
            source = LAB / name
            for mode in ("default", "forced-general"):
                with self.subTest(program=name, build=mode):
                    work = self.dir / (source.stem.replace("/", "-") + "-" + mode)
                    work.mkdir(parents=True, exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(base)
                    if mode == "forced-general":
                        env["AIL_UNIFIED_FORCE"] = "1"
                    else:
                        env.pop("AIL_UNIFIED_FORCE", None)
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                            "--syntax", "python", "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, name + " " + mode)

    def test_string_stmt_is_refused_by_name(self):
        source = LAB / "timeit" / "06_string_stmt.py"
        work = self.dir / "timeit-06-default"
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / "timeit06.out"
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True, timeout=600,
                               env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True, text=True,
                             timeout=120)
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("a string stmt needs exec", ran.stderr)

    def test_big_int_literal_is_a_compiler_refusal(self):
        source = LAB / "marshal" / "02_big_ints.py"
        work = self.dir / "marshal-02-default"
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / "marshal02.out"
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True, timeout=600,
                               env=env)
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("int64 constant out of range", built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
