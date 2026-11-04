"""The six small command-line tools of examples/apps: each one is compiled in the default mode and must
print what CPython prints (stdout and exit code) for every input in examples/apps/data.

jsonfield builds on the general path: a JSON object with mixed value types cannot be given one of the
typed path's declared value types.  The five tools in TYPED must build without the general-path note.

The colsum and jsonfield inputs that carry ints beyond int64 are compared with an --exact-int build:
the default int64 build stops loudly on those values.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APPS = ROOT.parent / "examples" / "apps"
DATA = APPS / "data"

CASES = {
    "wc.py": (
        ("wc_normal.txt", ()),
        ("wc_empty.txt", ()),
        ("wc_odd.txt", ()),
    ),
    "colsum.py": (
        ("colsum_normal.csv", ("value",)),
        ("colsum_empty.csv", ("value",)),
        ("colsum_odd.csv", ("value",)),
        ("colsum_normal.csv", ("missing",)),
    ),
    "topwords.py": (
        ("topwords_normal.txt", ("3",)),
        ("topwords_empty.txt", ("3",)),
        ("topwords_odd.txt", ("5",)),
    ),
    "grepn.py": (
        ("grepn_normal.txt", ("alpha",)),
        ("grepn_empty.txt", ("x",)),
        ("grepn_odd.txt", ("é",)),
    ),
    "jsonfield.py": (
        ("jsonfield_normal.jsonl", ("name",)),
        ("jsonfield_empty.jsonl", ("name",)),
        ("jsonfield_odd.jsonl", ("big",)),
    ),
    "hexdump.py": (
        ("hexdump_normal.bin", ()),
        ("hexdump_empty.bin", ()),
        ("hexdump_odd.bin", ()),
    ),
}

TYPED = ("wc.py", "colsum.py", "topwords.py", "grepn.py", "hexdump.py")

EXACT_INPUTS = {
    "colsum.py": (("colsum_odd.csv", ("value",)),),
    "jsonfield.py": (("jsonfield_odd.jsonl", ("big",)),),
}

DEFAULT_CASES = {
    tool: tuple((name, args) for name, args in cases if (name, args) not in EXACT_INPUTS.get(tool, ()))
    for tool, cases in CASES.items()
}


def compile_program(directory, tool, exact=False):
    Path(directory, tool).write_bytes((APPS / tool).read_bytes())
    exe = Path(directory, tool[:-3] + ("_exact" if exact else ""))
    command = [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", tool, "--syntax", "python"]
    if exact:
        command.append("--exact-int")
    command.extend(["-o", str(exe)])
    built = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900,
                           env=dict(os.environ, AIL_NO_CACHE="1"))
    return built, exe


def run_cpython(tool, args, data):
    return subprocess.run([sys.executable, tool] + list(args), cwd=APPS, input=data,
                          capture_output=True, timeout=300)


def run_binary(exe, args, data):
    return subprocess.run([str(exe)] + list(args), input=data, capture_output=True, timeout=300)


class ExamplesAppsTests(unittest.TestCase):
    def test_tools_match_cpython(self):
        for tool, cases in DEFAULT_CASES.items():
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, tool)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertTrue(exe.exists())
                for name, args in cases:
                    data = (DATA / name).read_bytes()
                    expected = run_cpython(tool, args, data)
                    ran = run_binary(exe, args, data)
                    self.assertEqual(expected.returncode, ran.returncode, name + " exit code")
                    self.assertEqual(expected.stdout, ran.stdout, name + " stdout")

    def test_typed_tools_build_without_the_note(self):
        for tool in TYPED:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, tool)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertNotIn("built on the general path", built.stderr)
                self.assertTrue(exe.exists())

    def test_beyond_int64_inputs_match_with_exact_int(self):
        for tool, cases in EXACT_INPUTS.items():
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as directory:
                built, exe = compile_program(directory, tool, exact=True)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertTrue(exe.exists())
                for name, args in cases:
                    data = (DATA / name).read_bytes()
                    expected = run_cpython(tool, args, data)
                    ran = run_binary(exe, args, data)
                    self.assertEqual(expected.returncode, ran.returncode, name + " exit code")
                    self.assertEqual(expected.stdout, ran.stdout, name + " stdout")


if __name__ == "__main__":
    unittest.main()
