"""stdfall2: `copy`, `timeit` and `marshal` in compiled programs (bundled stdlib).

The eighteen programs under lab/stdlib/{copy,timeit,marshal}/ exercise the
bundled AIL source modules `AIL_CURRENT/stdlib/copy.py`, `timeit.py` and
`marshal.py` against CPython 3.12.  Fourteen of them build with the default
command and with AIL_UNIFIED_FORCE=1 and print exactly what `python3` prints
on the same source (stdout and exit status); they are listed in PASSING.

The four remaining programs are recorded as named refusals in
lab/stdlib/stdfall2/RESULTS.md instead of being compared:

* copy/03_user_class_hooks.py and copy/04_user_class_plain.py build, then
  stop with `copy.Error: un(shallow)copyable object of type ... (class
  instances have no instance constructor in this compiler)`: this compiler
  cannot make an object of the original class, so it refuses by name.
* timeit/06_string_stmt.py uses `exec` for its string statement and is
  refused at build time (`exec() is not built`).
* marshal/02_big_ints.py cannot build: `2**70` is `int64 constant out of
  range` in the default build.

`marshal.dumps` is byte-exact for versions 0-2 (no object-reference flags);
version 3/4 need CPython's per-object refcount and interned bit, which this
compiler does not keep, so they are refused by name.
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

    def _build(self, source, name, force=False):
        work = self.dir / name
        work.mkdir(parents=True, exist_ok=True)
        program = work / Path(source).name
        shutil.copyfile(source, program)
        exe = work / (Path(source).stem + ".out")
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
        return built, exe, work

    def test_lab_programs_exist(self):
        self.assertEqual(len(self.sources), 18)
        self.assertEqual(len(PASSING), 14)
        for name in PASSING:
            self.assertTrue((LAB / name).is_file(), name)

    def test_programs_match_cpython(self):
        for name in PASSING:
            source = LAB / name
            for mode in ("default", "forced-general"):
                with self.subTest(program=name, build=mode):
                    built, exe, work = self._build(source, name.replace("/", "-") + "-" + mode,
                                                   force=(mode == "forced-general"))
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(source)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, name + " " + mode)

    def test_class_copy_is_refused_by_name(self):
        for name in ("copy/03_user_class_hooks.py", "copy/04_user_class_plain.py"):
            with self.subTest(program=name):
                built, exe, work = self._build(LAB / name, name.replace("/", "-") + "-refused")
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn("class instances have no instance constructor", ran.stderr)
                self.assertIn("copy.Error", ran.stderr)

    def test_string_stmt_is_refused_by_name(self):
        built, _exe, _work = self._build(LAB / "timeit" / "06_string_stmt.py",
                                         "timeit-06-refused")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("exec() is not built", built.stdout + built.stderr)

    def test_big_int_literal_is_a_compiler_refusal(self):
        built, _exe, _work = self._build(LAB / "marshal" / "02_big_ints.py",
                                         "marshal-02-refused")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("int64 constant out of range", built.stdout + built.stderr)

    def test_marshal_v4_is_refused_by_name(self):
        source = self.dir / "marshal_v4.py"
        source.write_text("import marshal\nprint(marshal.dumps([1]))\n")
        built, exe, work = self._build(source, "marshal-v4-refused")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                             text=True, timeout=120)
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("version 4 needs CPython's per-object refcount", ran.stderr)

    def test_marshal_loads_null_is_typeerror(self):
        source = self.dir / "marshal_null.py"
        source.write_text("import marshal\ntry:\n    marshal.loads(b'0')\n"
                          "except TypeError as e:\n    print(type(e).__name__, e)\n")
        built, exe, work = self._build(source, "marshal-null")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        expected = run_cpython(source)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(ran.stdout, expected.stdout)
        self.assertEqual(ran.returncode, expected.returncode)


if __name__ == "__main__":
    unittest.main()
