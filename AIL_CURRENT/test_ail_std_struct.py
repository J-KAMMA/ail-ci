"""struct1: `import struct` in compiled programs (bundled stdlib/struct.py) against CPython's struct.

The fourteen programs in lab/stdlib/struct/ use the byte orders `<`, `>`, `!`, `=` and native
`@`, repeat counts, the codes `x c b B ? h H i I l L q Q n N s p`, `pack`, `unpack`, `calcsize`,
`pack_into`, `unpack_from`, `iter_unpack` and the `Struct` class, plus the range, buffer and
argument errors caught through `struct.error`.  Every passing program is compiled with the default
command and with AIL_UNIFIED_FORCE=1 and run beside `python3` on the same source; stdout and the
exit status must agree.

11_int64_edges.py stops loudly at `Q = 2**64 - 1` (AIL ints are int64) and 14_floats.py stops
with the module's NotImplementedError for the float codes, so neither is compared; see
lab/stdlib/struct/RESULTS.md.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "struct"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_byte_orders.py",
    "02_repeat_and_counts.py",
    "03_int_codes.py",
    "04_long_codes.py",
    "05_bool_char_bytes.py",
    "06_roundtrip_mixed.py",
    "07_calcsize.py",
    "08_pack_into_unpack_from.py",
    "09_iter_unpack.py",
    "10_struct_class.py",
    "12_errors_range.py",
    "13_errors_buffer_args.py",
]


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibStructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-struct-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_byte_orders.py", "02_repeat_and_counts.py", "03_int_codes.py",
                          "04_long_codes.py", "05_bool_char_bytes.py", "06_roundtrip_mixed.py",
                          "07_calcsize.py", "08_pack_into_unpack_from.py", "09_iter_unpack.py",
                          "10_struct_class.py", "11_int64_edges.py", "12_errors_range.py",
                          "13_errors_buffer_args.py", "14_floats.py"])
        self.assertEqual(len(PASSING), 12)

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        for source in self.sources:
            if source.name not in PASSING:
                continue
            for mode in ("default", "forced-general"):
                with self.subTest(program=source.name, build=mode):
                    work = self.dir / (source.stem + "-" + mode)
                    work.mkdir(exist_ok=True)
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
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name + " " + mode)


if __name__ == "__main__":
    unittest.main()
