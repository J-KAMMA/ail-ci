"""`operator`: 12 real programs, compared with CPython 3.12.

The programs live in `lab/stdlib/operator/`.  Eleven build on the default path and on the forced
general path, and must print CPython's stdout and return its exit code; the twelfth
(`sequence_concat.py`) is refused by name for the in-place / sequence helpers that are still a
follow-up.  Each program is built with AIL_IR=0 and AIL_IR=1 and once more through the general path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "operator"

PROGRAMS = (
    "sort_records",
    "object_attrs",
    "method_pipeline",
    "mutate_map",
    "sequence_scan",
    "truthy_values",
    "arithmetic_ops",
    "comparison_dispatch",
    "functional_pipeline",
    "inventory_report",
    "bitmask_flags",
)
REFUSED = "sequence_concat"

CAPTURE = {
    "capture_methodcaller": r"""from operator import methodcaller
old, new = "a", "A"
f = methodcaller("replace", old, new)
old, new = "n", "N"
print(f("banana"))
sep = ","
s = methodcaller("split", sep)
sep = ";"
print(s("a,b;c"))
n = 6
pad = methodcaller("rjust", n, ".")
n = 3
print(pad("x"))
checkers = []
for suffix in [".txt", ".md"]:
    checkers.append(methodcaller("endswith", suffix))
print([f("notes.txt") for f in checkers])
""",
    "capture_itemgetter": r"""from operator import itemgetter
rows = [("a", 10, 100), ("b", 20, 200), ("c", 30, 300)]
i, j = 1, 2
g = itemgetter(i, j)
i, j = 2, 0
print(g(rows[0]))
getters = []
for p in [0, 2]:
    getters.append(itemgetter(p))
print([each(rows[0]) for each in getters])
""",
    "immediate_key_and_map": r"""from operator import itemgetter, methodcaller
rows = [("b", 2), ("a", 1), ("c", 3)]
i = 0
print(sorted(rows, key=itemgetter(i)))
i = 1
print(max(rows, key=itemgetter(i)), min(rows, key=itemgetter(i)))
print(list(map(itemgetter(1), rows)))
i = 0
g = itemgetter(i)
i = 1
print(sorted(rows, key=g))
names = ["a.md", "b.txt", "c.md"]
s = ".md"
print(list(filter(methodcaller("endswith", s), names)))
f = methodcaller("endswith", s)
s = ".txt"
print(list(filter(f, names)))
""",
}


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class OperatorTests(unittest.TestCase):
    def check(self, name, text, ir, general=False):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, AIL_IR="1" if ir else "0")
            env.pop("AIL_NO_GENERAL", None)
            env.pop("AIL_UNIFIED_FORCE", None)
            if general:
                env["AIL_UNIFIED_FORCE"] = "1"
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (IR=%s general=%s)\n%s%s"
                             % (name, env["AIL_IR"], general, built.stdout[-2000:], built.stderr[-2000:]))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode,
                             "%s (IR=%s general=%s) exit %d, CPython %d\n%s"
                             % (name, env["AIL_IR"], general, got.returncode, want.returncode,
                                got.stderr.decode("utf-8", "replace")[-1000:]))
            if got.stdout != want.stdout:
                a = got.stdout.decode("utf-8", "replace").splitlines()
                b = want.stdout.decode("utf-8", "replace").splitlines()
                for number, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (IR=%s general=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (name, env["AIL_IR"], general, number + 1, x, y))
                self.fail("%s (IR=%s general=%s): %d lines against %d"
                          % (name, env["AIL_IR"], general, len(a), len(b)))

    def test_programs_match_cpython(self):
        missing = [name for name in PROGRAMS if not (LAB / (name + ".py")).is_file()]
        if missing:
            self.skipTest("lab/stdlib/operator is not part of this tree: " + ", ".join(missing))
        for name in PROGRAMS:
            text = (LAB / (name + ".py")).read_text(encoding="utf-8")
            for general in (False, True):
                for ir in (False, True):
                    if general and not ir:
                        continue
                    with self.subTest(program=name, ir=ir, general=general):
                        self.check(name, text, ir, general)

    def test_arguments_are_captured_at_construction(self):
        for name, text in CAPTURE.items():
            for general in (False, True):
                for ir in (False, True):
                    if general and not ir:
                        continue
                    with self.subTest(program=name, ir=ir, general=general):
                        self.check(name, text, ir, general)

    def test_sequence_concat_is_refused_by_name(self):
        if not (LAB / (REFUSED + ".py")).is_file():
            self.skipTest("lab/stdlib/operator is not part of this tree")
        text = (LAB / (REFUSED + ".py")).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, REFUSED)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            for wanted in ("operator.iadd() with these arguments is not built",
                           "operator.concat() with these arguments is not built",
                           "operator.length_hint() with these arguments is not built",
                           "operator.index() with these arguments is not built"):
                self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
