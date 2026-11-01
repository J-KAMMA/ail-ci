"""Real programs that use `enum` the way ordinary Python code does, against CPython 3.12.

The nine programs that build in the default mode under `lab/stdlib/enum` are compiled with the Python
syntax and run; each must print CPython's stdout bytes and exit with its status.  A small edge program
covers `auto()` after a descending value, `B = A` aliases, an unhashable `in` value and an empty enum.
The other three programs there stay refused by name (a classmethod, an `__init__` on members, and the
functional API), and `lab/stdlib/enum/RESULTS.md` records them as follow-ups.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "enum"

PROGRAMS = (
    "empty_registry.py",
    "error_codes.py",
    "feature_flags.py",
    "file_modes.py",
    "http_status.py",
    "log_levels.py",
    "permissions.py",
    "planet_data.py",
    "traffic_light.py",
)

EDGE_PROGRAM = """\
from enum import Enum, auto

class Code(Enum):
    OK = 0
    MISSING = 404
    DENIED = 403
    GHOST = auto()
    SAME = MISSING

class Empty(Enum):
    pass

def main():
    print([m.name for m in Code], list(Code.__members__))
    print(Code.GHOST.value, Code.SAME.name, Code.SAME is Code.MISSING)
    print(404 in Code, 405 in Code, Code.GHOST in Code)
    values = [404, 405, 999]
    for value in values:
        print(value in Code)
    holder = {"value": 405}
    print(holder["value"] in Code)
    try:
        [1] in Code
    except TypeError as error:
        print("TypeError", error)
    try:
        Empty(1)
    except TypeError as error:
        print("TypeError", error)

main()
"""


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, AIL_NO_CACHE="1"))
    return built, source, exe


class LabPrograms(unittest.TestCase):
    def check_program(self, name, text, prefix):
        with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, prefix + Path(name).stem)
            self.assertEqual(built.returncode, 0, "%s\n%s%s" % (name, built.stdout, built.stderr))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)],
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode,
                             "%s: %s" % (name, got.stderr[-400:]))
            if got.stdout != want.stdout:
                mine = got.stdout.decode().splitlines()
                theirs = want.stdout.decode().splitlines()
                for number, (a, b) in enumerate(zip(mine, theirs), 1):
                    if a != b:
                        self.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (name, number, a, b))
                self.fail("%s: %d lines against %d" % (name, len(mine), len(theirs)))

    def test_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest("lab/stdlib/enum is not part of this tree")
        for name in PROGRAMS:
            self.check_program(name, (LAB / name).read_text(encoding="utf-8"), "p_")

    def test_edge_cases_match_cpython(self):
        self.check_program("enum_edges.py", EDGE_PROGRAM, "edge_")


if __name__ == "__main__":
    unittest.main()
