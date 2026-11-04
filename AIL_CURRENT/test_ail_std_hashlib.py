"""The hashlib / hmac programs of lab/stdlib/hashlib, compared with CPython 3.12.

Eleven programs build on the typed path in the default mode and must print exactly what CPython
prints, with no general-path note. `11_digest_integer.py` reads an 8-byte unsigned digest slice whose
value is beyond int64, so it is built with `--exact-int` (exact big ints) and must match CPython as
well. Programs that read stdin are run with their file from `data/`.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "hashlib"
DATA = LAB / "data"

TYPED = (
    "01_checksum_stdin.py",
    "02_text_digests.py",
    "03_new_by_name.py",
    "04_blake2_options.py",
    "05_copy_running.py",
    "06_hash_properties.py",
    "07_hmac_messages.py",
    "08_pbkdf2_key.py",
    "09_content_store.py",
    "10_merkle_root.py",
    "12_empty_inputs.py",
)

EXACT = ("11_digest_integer.py",)

STDIN = {
    "01_checksum_stdin.py": "checksum_input.bin",
    "02_text_digests.py": "digest_text.txt",
}

REFUSED = {}


def input_bytes(name):
    source = STDIN.get(name)
    if source is None:
        return b""
    return (DATA / source).read_bytes()


def build_source(directory, name, extra=()):
    source = Path(directory) / name
    shutil.copy2(LAB / name, source)
    exe = Path(directory) / (name[:-3] + "_bin")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["AIL_NO_CACHE"] = "1"
    built = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python",
         "-o", exe.name, *extra],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env,
    )
    return built, source, exe


def run_source(source, payload):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(source)], input=payload, capture_output=True, timeout=300,
                          env=env)


def run_exe(exe, payload):
    return subprocess.run([str(exe)], input=payload, capture_output=True, timeout=300)


class StdlibHashlibTests(unittest.TestCase):
    def test_typed_programs_match_cpython(self):
        for name in TYPED:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                payload = input_bytes(name)
                built, source, exe = build_source(directory, name)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-2000:])
                self.assertNotIn("built on the general path", built.stderr, name)
                expected = run_source(source, payload)
                self.assertEqual(expected.returncode, 0, expected.stderr[-500:])
                ran = run_exe(exe, payload)
                self.assertEqual(ran.returncode, expected.returncode, ran.stderr[-500:])
                self.assertEqual(ran.stdout, expected.stdout, ran.stderr[-500:])

    def test_exact_int_program_matches_cpython(self):
        for name in EXACT:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                payload = input_bytes(name)
                built, source, exe = build_source(directory, name, ("--exact-int",))
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-2000:])
                expected = run_source(source, payload)
                self.assertEqual(expected.returncode, 0, expected.stderr[-500:])
                ran = run_exe(exe, payload)
                self.assertEqual(ran.returncode, expected.returncode, ran.stderr[-500:])
                self.assertEqual(ran.stdout, expected.stdout, ran.stderr[-500:])

    def test_refused_programs_keep_their_name(self):
        for name, needle in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, source, exe = build_source(directory, name)
                self.assertNotEqual(built.returncode, 0, built.stdout)
                self.assertIn(needle, built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
