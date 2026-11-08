"""stdfall2: `copy`, `timeit` and `marshal` in compiled programs (bundled stdlib).

The eighteen programs under lab/stdlib/{copy,timeit,marshal}/ exercise the
bundled AIL source modules `AIL_CURRENT/stdlib/copy.py`, `timeit.py` and
`marshal.py` against CPython 3.12.  Nine of them build with the default
command and with AIL_UNIFIED_FORCE=1 and print exactly what `python3` prints
on the same source (stdout and exit status); they are listed in PASSING.

The other nine programs are recorded as named refusals in
lab/stdlib/stdfall2/RESULTS.md instead of being compared:

* copy/03_user_class_hooks.py and copy/04_user_class_plain.py build, then
  stop with `copy.Error: un(shallow)copyable object of type ... (class
  instances have no instance constructor in this compiler)`: this compiler
  cannot make an object of the original class, so it refuses by name.
* timeit/06_string_stmt.py uses `exec` for its string statement and is
  refused at build time (`exec() is not built`).
* the six marshal programs call `marshal.dumps(x)` without a version, whose
  CPython default is 4.  Version 3/4 need CPython's per-object refcount and
  interned bit, which this compiler does not keep, so the `version` argument
  is required and an omitted one is a build-time refusal
  (`marshal.dumps() called without a required argument version`).
* marshal/02_big_ints.py additionally cannot build: `2**70` is `int64
  constant out of range` in the default build.

`marshal.dumps(x, 0/1/2)` is byte-exact (no object-reference flags); an
explicit version 3/4 is refused by name at run time.
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
]

MARSHAL = [
    "marshal/01_ints_bool_none.py",
    "marshal/02_big_ints.py",
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
        self.assertEqual(len(PASSING), 9)
        self.assertEqual(len(MARSHAL), 6)
        for name in PASSING + MARSHAL:
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

    def test_deepcopy_set_elements_are_new_objects(self):
        source = self.dir / "copy_set_elements.py"
        source.write_text(
            "import copy\n"
            "inner = frozenset({1, 2})\n"
            "s = {inner}\n"
            "fs = frozenset({frozenset({3, 4})})\n"
            "ds = copy.deepcopy(s)\n"
            "df = copy.deepcopy(fs)\n"
            "print(ds is s, ds == s, s.pop() is ds.pop())\n"
            "a = sorted(fs)[0]\n"
            "b = sorted(df)[0]\n"
            "print(df is fs, df == fs, a is b, a == b)\n")
        expected = run_cpython(source)
        for mode in ("default", "forced-general"):
            with self.subTest(build=mode):
                built, exe, work = self._build(source, "copy-set-elements-" + mode,
                                               force=(mode == "forced-general"))
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode, ran.stderr)
                self.assertEqual(ran.stdout, expected.stdout)

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
        text = built.stdout + built.stderr
        self.assertTrue("int64 constant out of range" in text
                        or "called without a required argument version" in text, text)

    def test_marshal_default_version_is_a_build_time_refusal(self):
        for name in MARSHAL:
            if name.endswith("02_big_ints.py"):
                continue
            with self.subTest(program=name):
                built, _exe, _work = self._build(LAB / name, name.replace("/", "-") + "-refused")
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                text = built.stdout + built.stderr
                self.assertIn("marshal.dumps() called without a required argument version",
                              text)

    def test_marshal_explicit_versions_0_to_2_are_byte_exact(self):
        source = self.dir / "marshal_v012.py"
        source.write_text(
            "import marshal\n"
            "vals = [None, True, False, 0, 1, -1, 42, 2**40, 9223372036854775807,\n"
            "        -9223372036854775807 - 1, -0.0, 1.5, 1e300, 'abc', 'caf\\xe9',\n"
            "        b'xy', [1, 'a'], (1, 2), {'k': 1}]\n"
            "for x in vals:\n"
            "    for v in (0, 1, 2):\n"
            "        raw = marshal.dumps(x, v)\n"
            "        back = marshal.loads(raw)\n"
            "        print(v, type(back).__name__, back == x, raw.hex())\n")
        built, exe, work = self._build(source, "marshal-v012")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        expected = run_cpython(source)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(ran.returncode, expected.returncode)
        self.assertEqual(ran.stdout, expected.stdout)

    def test_marshal_explicit_v4_is_refused_by_name(self):
        source = self.dir / "marshal_v4.py"
        source.write_text("import marshal\ntry:\n    marshal.dumps([1], 4)\n"
                          "except ValueError as e:\n    print(type(e).__name__, e)\n")
        built, exe, work = self._build(source, "marshal-v4-refused")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("ValueError marshal.dumps: version 4 needs CPython's per-object refcount",
                      ran.stdout)

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
