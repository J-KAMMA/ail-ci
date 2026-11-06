"""Crate examples: three Rust crates called from Python syntax, on CPython and in an AIL binary.

Each `examples/crate/<name>` is built with `ail_cargo.py build` into a temporary directory, then the same
`main.py` runs twice: under `python3` through the ctypes shim (the generated stub is pointed at the
cdylib) and as the executable `ail_chatgpt.py compile` builds (the generated stub links the staticlib).
The stdout and the exit status must be equal.

The crates have no dependencies, so cargo runs `--offline`.  A test is skipped, naming the missing tool,
when cargo or a C compiler is not installed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / "ail_chatgpt.py"
CARGO_TOOL = ROOT / "ail_cargo.py"
CRATES = REPO / "examples" / "crate"
CARGO = shutil.which("cargo")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

CASES = {
    "fnvhash": {"header": "fnvhash/fnvhash.h", "flags": ["--exact-int"]},
    "textstat": {"header": "textstat/textstat.h", "check": "stats=negative:ValueError"},
    "rle": {"header": "rle/rle.h"},
    "wordbag": {"header": "wordbag/wordbag.h"},
    "slugify": {"header": "slugify/slugify.h"},
    "walk": {"header": "walk/walk.h"},
    "bits": {"header": "bits/bits.h"},
}


def run(command, cwd, env=None, timeout=900):
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)


@unittest.skipUnless(CARGO and CC, "cargo and a C compiler are required")
class CrateExampleTests(unittest.TestCase):
    def example(self, name):
        case = CASES[name]
        source = CRATES / name
        self.assertTrue((source / "main.py").is_file(), source / "main.py")
        with tempfile.TemporaryDirectory(prefix="ail-crate-example-") as directory:
            work = Path(directory)
            out = work / "out"
            env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
                       CARGO_TARGET_DIR=str(work / "target"))
            command = [sys.executable, str(CARGO_TOOL), "build", str(source), "-o", str(out),
                       "--header", str(source / (name + ".h"))]
            if "check" in case:
                command += ["--check", case["check"]]
            built = run(command, work, env=env)
            self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
            stubs = out / (name + "_ffi.py")
            original = stubs.read_text(encoding="utf-8")
            self.assertIn("link('./lib%s.a')" % name, original.replace('"', "'"))

            for module in sorted(source.glob("*.py")):
                shutil.copyfile(module, out / module.name)
            main_source = (out / "main.py").read_text(encoding="utf-8")
            cpython_main = "main.py"
            if "./lib%s.a" % name in main_source:
                cpython_main = "main_cpython.py"
                (out / cpython_main).write_text(
                    main_source.replace("./lib%s.a" % name, "./lib%s.so" % name), encoding="utf-8")
            shared = original.replace("./lib%s.a" % name, "./lib%s.so" % name)
            stubs.write_text(shared, encoding="utf-8")
            expected = run([sys.executable, "-B", cpython_main], out, env=env)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            stubs.write_text(original, encoding="utf-8")

            exe = out / "main.out"
            compiled = run([sys.executable, "-B", str(CLI), "compile", "main.py", "-o", str(exe)]
                           + case.get("flags", []), out, env=dict(env, AIL_NO_CACHE="1"))
            self.assertEqual(compiled.returncode, 0, compiled.stderr + compiled.stdout)
            got = run([str(exe)], out, env=env)
            self.assertEqual(got.returncode, expected.returncode, got.stderr)
            self.assertEqual(got.stdout, expected.stdout)
            return got.stdout

    def test_fnvhash(self):
        text = self.example("fnvhash")
        self.assertEqual(text.splitlines(), [
            "14695981039346656037",
            "12638187200555641996",
            "5808125746575713061",
            "11831194018420276491",
            "6462304499243991330",
        ])

    def test_textstat(self):
        text = self.example("textstat")
        self.assertEqual(text.splitlines(), [
            "0 0 0",
            "2 3 14",
            "2 2 8",
            "ValueError: stats failed with -1",
        ])

    def test_rle(self):
        text = self.example("rle")
        self.assertEqual(text.splitlines(), [
            "20 8 True",
            "3 6 True",
            "360 720 True",
            "-1",
        ])

    def test_wordbag(self):
        text = self.example("wordbag")
        self.assertEqual(text.splitlines(), [
            "0 0",
            "2 1 0",
            "1",
        ])

    def test_slugify(self):
        text = self.example("slugify")
        self.assertEqual(text.splitlines(), [
            "11 hello-world",
            "3 a-b",
            "12 already-slug",
            "0 ",
            "need 12",
            "3 caf",
            "need 6",
        ])

    def test_walk(self):
        text = self.example("walk")
        self.assertEqual(text.splitlines(), [
            "step 0",
            "step 1",
            "step 2",
            "step 3",
            "sum 14",
            "empty 0",
            "fail 0",
            "fail 1",
            "fail 2",
            "fail 3",
            "caught: stop at 3",
            "done",
        ])

    def test_bits(self):
        text = self.example("bits")
        self.assertEqual(text.splitlines(), [
            "0 0",
            "1 1",
            "11 3",
            "2147483648 1",
            "9223372036854775807 63",
            "3 878082066",
            "2147483648 3735928559",
        ])


if __name__ == "__main__":
    unittest.main()
