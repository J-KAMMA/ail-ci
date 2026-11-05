"""xdrlib1: `import xdrlib` in compiled programs (bundled stdlib/xdrlib.py) against CPython's xdrlib.

The ten programs in lab/stdlib/xdrlib/ pack with `xdrlib.Packer` and print
`get_buffer().hex()`, unpack with `xdrlib.Unpacker` and print the values.  They cover
pack_uint/pack_int/pack_enum/pack_bool/pack_hyper/pack_uhyper/pack_float/pack_double/
pack_fstring/pack_fopaque/pack_string/pack_opaque/pack_bytes/pack_list/pack_farray/pack_array
and the matching unpack methods, `reset`, `get_position`, `set_position`, `get_buffer`, `done()`,
and the four error kinds (xdrlib.Error, EOFError, xdrlib.ConversionError, ValueError) printed as
`type(e).__name__` and `str(e)`.  Every passing program is compiled with the default command and
with AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the exit status
must agree.

CPython 3.12 prints a DeprecationWarning for `import xdrlib`; only stdout and the exit status are
compared.  03_uhyper_max.py has one CPython value beyond int64 (18446744073709551615).  It passes
only if AIL prints that text or exits non-zero with an `OverflowError` line on stderr.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "xdrlib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_uint_int_enum.py",
    "02_bool_hyper.py",
    "04_float_double.py",
    "05_strings_opaque.py",
    "06_arrays.py",
    "07_positions.py",
    "08_done_eof.py",
    "09_conversion_errors.py",
    "10_record.py",
]

BEYOND_INT64 = ["03_uhyper_max.py"]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibXdrlibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-xdrlib-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build_and_run(self, source, mode):
        work = self.dir / (source.stem + "-" + mode)
        work.mkdir(exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / (source.stem + ".out")
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "forced-general":
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
        return ran

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_uint_int_enum.py", "02_bool_hyper.py", "03_uhyper_max.py",
                          "04_float_double.py", "05_strings_opaque.py", "06_arrays.py",
                          "07_positions.py", "08_done_eof.py", "09_conversion_errors.py",
                          "10_record.py"])
        self.assertEqual(len(PASSING), 9)

    def test_programs_match_cpython(self):
        for source in self.sources:
            if source.name not in PASSING:
                continue
            expected = run_cpython(source)
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    ran = self.build_and_run(source, mode)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)

    def test_beyond_int64_prints_or_stops_loudly(self):
        for source in self.sources:
            if source.name not in BEYOND_INT64:
                continue
            expected = run_cpython(source)
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    ran = self.build_and_run(source, mode)
                    if ran.stdout == expected.stdout:
                        continue
                    self.assertNotEqual(ran.returncode, 0,
                                        source.name + " " + mode + " printed a different value")
                    self.assertIn("OverflowError", ran.stderr,
                                  "%s %s did not stop loudly:\n%s"
                                  % (source.name, mode, ran.stderr))


if __name__ == "__main__":
    unittest.main()
