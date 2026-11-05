"""G5b: `import tomllib` in compiled programs (bundled stdlib/tomllib) against CPython's tomllib.

The twelve programs in lab/stdlib/tomllib/ parse TOML the way ordinary code does: scalar
types, tables and dotted keys, arrays and arrays of tables, inline tables, date-times,
parse_float=decimal.Decimal, load() from a bytes reader, the TOMLDecodeError cases and an
integer beyond int64.  Eight of them build and match `python3` in the default build and
with AIL_UNIFIED_FORCE=1; the other four stop on compiler limits recorded in
lab/stdlib/tomllib/RESULTS.md and are not built here.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "tomllib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

ALL_PROGRAMS = [
    "01_scalars.py",
    "02_tables.py",
    "03_arrays.py",
    "04_datetimes.py",
    "05_parse_float.py",
    "06_config.py",
    "07_load_bytes.py",
    "08_errors.py",
    "09_big_int.py",
    "10_multiline.py",
    "11_keys.py",
    "12_inline_arrays.py",
]

# Programs that build and print what CPython prints, exit status included.
PASSING = [
    "01_scalars.py",
    "02_tables.py",
    "03_arrays.py",
    "05_parse_float.py",
    "06_config.py",
    "07_load_bytes.py",
    "11_keys.py",
    "12_inline_arrays.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibTomllibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-tomllib-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], ALL_PROGRAMS)

    def test_programs_match_cpython(self):
        for source in self.sources:
            if source.name not in PASSING:
                continue
            for label, force in (("default", False), ("force", True)):
                with self.subTest(program=source.name, build=label):
                    work = self.dir / (source.stem + "-" + label)
                    work.mkdir(exist_ok=True)
                    program = work / source.name
                    shutil.copyfile(source, program)
                    exe = work / (source.stem + ".out")
                    env = dict(os.environ, AIL_NO_CACHE="1")
                    env.pop("PYTHONPATH", None)
                    if force:
                        env["AIL_UNIFIED_FORCE"] = "1"
                    built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                            "--syntax", "python", "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name)


if __name__ == "__main__":
    unittest.main()
