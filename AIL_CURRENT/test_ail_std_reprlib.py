"""Bundled `reprlib` in compiled programs: the lab/stdlib/reprlib programs against CPython 3.12.

Each program is ordinary Python. CPython runs it as the oracle; the compiled program prints the
same bytes and exits with the same status. The default build and the forced general build
(`AIL_UNIFIED_FORCE=1`) are both checked. `12_bigints.py` is not built: its `10 ** 50` and `2 ** 70`
are int64 constants out of range in both builds, a loud stop the brief allows.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "reprlib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

RECURSIVE_IDENTITY = '''import reprlib


def raw(self):
    return "N(%s, %r)" % (self.name, self.child)


render = reprlib.recursive_repr()(raw)


class Node:
    def __init__(self, name, child):
        self.name = name
        self.child = child

    def __eq__(self, other):
        return type(other).__name__ == 'Node' and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return render(self)


class Unhashable:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self is other

    __hash__ = None

    def __repr__(self):
        return "U(%s)" % self.name


a = Node("a", None)
a.child = Node("a", None)
print(repr(a))
print(repr(Unhashable("u")))
'''

PASSING = [
    "01_long_list.py",
    "02_tuples_sets.py",
    "03_dicts.py",
    "04_strings.py",
    "05_nested_maxlevel.py",
    "06_limits_attrs.py",
    "07_limits_kwargs.py",
    "08_indent.py",
    "09_arepr.py",
    "10_subclasses.py",
    "11_recursive.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibReprlibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-reprlib-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_long_list.py", "02_tuples_sets.py", "03_dicts.py",
                          "04_strings.py", "05_nested_maxlevel.py", "06_limits_attrs.py",
                          "07_limits_kwargs.py", "08_indent.py", "09_arepr.py",
                          "10_subclasses.py", "11_recursive.py", "12_bigints.py"])

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for name in PASSING:
            source = PROGRAMS / name
            expected = run_cpython(source)
            for forced in (False, True):
                with self.subTest(program=name, forced=forced):
                    work = self.dir / (source.stem + ("_force" if forced else "_default"))
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(base)
                    if forced:
                        env["AIL_UNIFIED_FORCE"] = "1"
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

    def test_recursive_identity(self):
        source = self.dir / "recursive_identity.py"
        source.write_text(RECURSIVE_IDENTITY)
        expected = run_cpython(source)
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for forced in (False, True):
            with self.subTest(forced=forced):
                work = self.dir / ("recursive_identity" + ("_force" if forced else "_default"))
                work.mkdir(exist_ok=True)
                program = work / source.name
                shutil.copyfile(source, program)
                exe = work / "recursive_identity.out"
                env = dict(base)
                if forced:
                    env["AIL_UNIFIED_FORCE"] = "1"
                built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                        "--syntax", "python", "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode, ran.stderr)
                self.assertEqual(ran.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()
