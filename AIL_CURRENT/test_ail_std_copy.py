"""copy.copy / copy.deepcopy on the general path (genlib.py + prelude_genlib.py + safetyrt.py).

The twelve programs in lab/stdlib/copy are compiled with the default build and with AIL_UNIFIED_FORCE=1
(the general path), run, and must print exactly what CPython 3.12 prints and exit with the same status.
A synthetic program adds the boundaries the examples do not reach: immutable scalars, bytes, bytearray,
frozenset, a tuple/list cycle, shared references and an explicit memo (including bad memo values).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "copy"

EDGES = r"""import copy
from copy import copy as cp, deepcopy as dc

def gen():
    yield 1

def main() -> None:
    for value in (5, 2.5, "text", b"raw", (1, 2), frozenset({1, 2}), None, True):
        a = cp(value)
        b = dc(value)
        print(type(value).__name__, a == value, b == value, a is value, b is value)
    for value in ([1, 2], {"a": 1}, {1, 2}):
        a = cp(value)
        b = dc(value)
        print(type(value).__name__, a == value, b == value, a is value, b is value)
    a = bytearray(b"abc")
    b = cp(a)
    c = dc(a)
    b[0] = 120
    c[1] = 121
    print(a, b, c)
    print(a is b, a is c, b is c)
    shared = [1]
    source = [shared, shared]
    memo = {}
    one = dc(source, memo)
    print(one[0] is one[1], len(memo))
    two = dc(source, memo)
    print(two[0] is one[0], len(memo))
    ring = []
    ring.append(ring)
    clone = dc(ring)
    print(clone[0] is clone)
    pair = ([],)
    pair[0].append(pair)
    back = dc(pair)
    print(back[0][0] is back)
    table = {("a", 1): [1]}
    shallow_table = cp(table)
    for key in shallow_table:
        print("table", key)
    deep_table = dc({("b", 2): [2]})
    for key in deep_table:
        print("deep", key)
    g = gen()
    try:
        cp(g)
    except Exception as exc:
        print(type(exc).__name__, exc)
    try:
        dc({"g": g})
    except Exception as exc:
        print(type(exc).__name__, exc)
    for bad in (5, [], "x"):
        try:
            dc([], bad)
        except Exception as exc:
            print(type(exc).__name__)
    for call in (lambda: cp(), lambda: dc(), lambda: cp([], []), lambda: dc([], None, [], "x")):
        try:
            call()
        except Exception as exc:
            print(type(exc).__name__)

main()
"""


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class CompiledPrograms(unittest.TestCase):
    def compare(self, name, text, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 0, "%s %r\n%s%s" % (name, env, built.stdout, built.stderr))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s %r\n%s" % (
                name, env, got.stderr.decode("utf-8", "replace")[-1000:]))
            if got.stdout != want.stdout:
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for line, (x, y) in enumerate(zip(a, b), 1):
                    if x != y:
                        self.fail("%s %r line %d:\n  compiled: %r\n  CPython:  %r" % (name, env, line, x, y))
                self.fail("%s %r: %d lines against %d" % (name, env, len(a), len(b)))

    def test_lab_programs_match_cpython(self):
        programs = sorted(PROGRAMS.glob("p*.py"))
        self.assertEqual(len(programs), 12, programs)
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            for program in programs:
                with self.subTest(program=program.name, env=env):
                    self.compare(program.stem, program.read_text(encoding="utf-8"), **env)

    def test_edge_cases_match_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                self.compare("copy_edges", EDGES, **env)

    def test_copy_protocol_is_refused(self):
        text = """import copy
class WithCopy:
    def __init__(self):
        self.v = [1]
    def __copy__(self):
        return "copied"
    def __deepcopy__(self, memo):
        return "deep"
def main():
    print(copy.copy(WithCopy()))
main()
"""
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                with tempfile.TemporaryDirectory() as directory:
                    built, _, _ = compile_python(directory, text, "copy_protocol", **env)
                    self.assertNotEqual(built.returncode, 0, "%s %r\n%s%s" % (
                        "copy_protocol", env, built.stdout, built.stderr))
                    self.assertIn("copy protocol needs method dispatch and _reconstruct",
                                  built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
