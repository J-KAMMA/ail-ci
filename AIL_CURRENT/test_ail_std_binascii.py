"""G5a: `import binascii` in compiled programs (bundled stdlib/binascii.py) against CPython's binascii.

The twelve programs in lab/stdlib/binascii/ use hexlify / b2a_hex with and without separators,
unhexlify / a2b_hex on bytes and ASCII str, b2a_base64 with and without a newline, a2b_base64 with
and without strict_mode, crc32 over chunks, crc_hqx, the exact binascii.Error texts, and a file
checksum.  Eleven are compared with `python3` on stdout and the exit status in both the default
build and AIL_UNIFIED_FORCE=1; 11_crc_big asks for a value beyond int64, so it is only checked to
build and to stop loudly, which the brief allows.  A fourth test compiles an embedded program of
boundary values (empty input, bytes_per_sep 0/negative/int32 edges, bytearray aliasing, and values
arriving through an argument, a list item, an attribute and a dict value) and compares it the same way.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "binascii"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

ALL = ["01_hex_basic.py", "02_hex_sep.py", "03_unhex.py", "04_hex_errors.py",
       "05_base64_encode.py", "06_base64_decode.py", "07_base64_strict.py",
       "08_base64_errors.py", "09_crc32.py", "10_crc32_values.py",
       "11_crc_big.py", "12_checksum.py"]
MATCHING = [name for name in ALL if name != "11_crc_big.py"]

# Boundaries the twelve lab programs do not reach: empty input, a negative or zero bytes_per_sep,
# the int32 width of bytes_per_sep, a non-buffer and a wrong-typed seed, bytearray aliasing, and
# the values arriving through an argument, a list item, an attribute and a dict value.
EDGE = r'''import binascii


class Holder:
    def __init__(self):
        self.data = b"hello"
        self.sep = b":"


def h(data, sep, n):
    return binascii.hexlify(data, sep, n)


def c(data, seed):
    return binascii.crc32(data, seed)


def t(data, sep, bps):
    try:
        print(binascii.hexlify(data, sep, bps))
    except Exception as exc:
        print(type(exc).__name__, exc)


def main() -> None:
    o = Holder()
    items = [b"abc", b"defg"]
    sizes = [1, 2, 3]
    seeds = {"a": 7, "b": 9}
    print(binascii.hexlify(b""))
    print(binascii.hexlify(b"\x00\xff\x10"))
    print(binascii.hexlify(b"abcdef", b"-", -2))
    print(binascii.hexlify(b"abcdef", b"-", 0))
    print(binascii.hexlify(b"abcd", b"-", 2147483647))
    print(binascii.hexlify(b"abcd", b"-", -2147483648))
    t(b"abcd", b"-", 2147483648)
    t(b"abcd", b"-", 1.5)
    t([1, 2], b"-", 1)
    print(h(o.data, o.sep, sizes[1]), h(items[1][1:3], o.sep, len(items[0])))
    print(c(o.data, seeds["a"]), c(items[0], 2 ** 63 - 1))
    print(binascii.crc32(b"hello", -1), binascii.crc32(b"hello", 2 ** 32))
    print(binascii.crc_hqx(b"abc", 70000), binascii.crc_hqx(b"abc", -1))
    print(binascii.unhexlify(b""), binascii.a2b_hex(bytearray(b"0102")))
    print(binascii.b2a_base64(b"", newline=False), binascii.b2a_base64(b"ab"))
    print(binascii.a2b_base64(b""), binascii.a2b_base64(b"YWJj"))
    buf = bytearray(b"ab")
    before = binascii.crc32(buf)
    print(before, binascii.b2a_base64(buf), binascii.hexlify(buf))
    buf[0] = 122
    print(binascii.crc32(buf) != before, binascii.hexlify(buf))


main()
'''


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdBinasciiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-binascii-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources], ALL)

    def build(self, source, work, forced):
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / (source.stem + ".out")
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if forced:
            env["AIL_UNIFIED_FORCE"] = "1"
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=600, env=env)
        return built, program, exe, work

    def test_programs_match_cpython(self):
        for forced in (False, True):
            label = "forced" if forced else "default"
            for name in MATCHING:
                source = PROGRAMS / name
                with self.subTest(program=name, build=label):
                    work = self.dir / label / source.stem
                    built, program, exe, work = self.build(source, work, forced)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s (%s)" % (name, label))

    def test_edge_values_match_cpython(self):
        source = self.dir / "edge.py"
        source.write_text(EDGE, encoding="utf-8")
        for forced in (False, True):
            label = "forced" if forced else "default"
            with self.subTest(build=label):
                work = self.dir / label / "edge"
                built, program, exe, work = self.build(source, work, forced)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                expected = run_cpython(program)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode,
                                 "edge exit\nexpected stderr: %s\nactual stderr: %s"
                                 % (expected.stderr, ran.stderr))
                self.assertEqual(ran.stdout, expected.stdout, "edge (%s)" % label)

    def test_big_value_stops_loudly(self):
        source = PROGRAMS / "11_crc_big.py"
        for forced in (False, True):
            label = "forced" if forced else "default"
            with self.subTest(program=source.name, build=label):
                work = self.dir / label / source.stem
                built, program, exe, work = self.build(source, work, forced)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                                     text=True, timeout=120)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn("overflow", ran.stderr)


if __name__ == "__main__":
    unittest.main()
