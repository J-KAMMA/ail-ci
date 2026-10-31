"""Bound methods of builtin objects taken as values (boundbuiltin.py), compared with CPython 3.12.

CPython's Lib/keyword.py has `iskeyword = frozenset(kwlist).__contains__` at module level.  The general
path had no bound-method value for a builtin object: the read failed at run time with `AttributeError:
'frozenset' object has no attribute '__contains__'`.  Now `frozenset(xs).__contains__`, `s.add`, `l.append`,
`",".join`, `d.get`, `str.upper` ... stored in a name and called later behave as in CPython, at module level
and in functions, in one file and across files, on the default build and with AIL_UNIFIED_FORCE=1.

B1  a single file: bound methods of set / frozenset / list / dict / str, and unbound `str.upper`
B2  the keyword.py shape across two files (CPython's Lib/keyword.py, renamed: CPython has `keyword` loaded before a script directory is searched)
B3  a name that a class of the program also uses stays the class's; a literal receiver of such a name is refused
B4  a method outside the supported table, read from a literal, is refused with `write instead`
B5  an exception raised while an imported module runs its top level is loud: the output so far, stderr, exit 1
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

SINGLE = '''kwlist = ["for", "if", "in"]
iskeyword = frozenset(kwlist).__contains__
seen = set()
add = seen.add
items = []
push = items.append
join = ",".join
getter = {"a": 1}.get
up = str.upper
strip = str.strip
total = [3, 1, 2].count
d = {}
setd = d.setdefault
pairs = {"k": "v"}.items


def f(xs):
    out = []
    ap = out.append
    for x in xs:
        ap(x * 2)
    h = {"k": "v"}.items
    print(list(h()))
    return out


add(1)
add(2)
add(1)
push("a")
push("b")
print(iskeyword("for"), iskeyword("x"))
print(sorted(seen), items, join(["p", "q"]), join(items))
print(getter("a"), getter("b"), getter("b", 7))
print(up("abc"), strip("  z "), total(1))
print(setd("m", []), setd("m", 5), d)
print(f([1, 2, 3]))
print(list(pairs()))
mk = lambda s: s.lower
print(mk("ABC")())
print([g("x") for g in [str.upper, str.title]])
print(list(map(str.strip, [" a ", "b "])))
print(sorted(["b", "A"], key=str.lower))


class P:
    def __init__(self):
        self.val = 5


print(P().val)
'''

KEYWORD_MAIN = '''import kwmod
print(kwmod.iskeyword("for"), kwmod.iskeyword("x"))
print(len(kwmod.kwlist), kwmod.issoftkeyword("_"))
'''

KEYWORD_MOD = '''__all__ = ["iskeyword", "issoftkeyword", "kwlist", "softkwlist"]
kwlist = ["False", "None", "True", "and", "as", "assert", "for", "if", "in", "not", "or", "while"]
softkwlist = ["_", "case", "match"]
iskeyword = frozenset(kwlist).__contains__
issoftkeyword = frozenset(softkwlist).__contains__
'''


class BoundBuiltin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-bound-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, files):
        for name, text in files.items():
            (self.dir / name).write_text(text, encoding="utf-8")

    def build(self, forced):
        env = dict(os.environ)
        env.pop("AIL_NO_GENERAL", None)
        env.pop("AIL_PATH", None)
        env["AIL_UNIFIED_FORCE"] = "1" if forced else ""
        exe = self.dir / ("out_f" if forced else "out")
        if exe.exists():
            exe.unlink()
        built = subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "-o", str(exe)], cwd=self.dir,
                               capture_output=True, text=True, timeout=600, env=env)
        return built, exe

    def same_as_cpython(self, files):
        self.write(files)
        want = subprocess.run([sys.executable, "-B", "main.py"], cwd=self.dir, capture_output=True, timeout=60)
        self.assertEqual(want.returncode, 0, want.stderr.decode())
        for forced in (False, True):
            built, exe = self.build(forced)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, want.stdout, "forced=%s" % forced)
            self.assertEqual(ran.returncode, 0, ran.stderr.decode())

    def refused(self, files, *needles):
        self.write(files)
        built, exe = self.build(False)
        self.assertNotEqual(built.returncode, 0, built.stdout)
        self.assertFalse(exe.exists())
        for needle in needles:
            self.assertIn(needle, built.stderr)
        self.assertNotIn("Traceback", built.stderr)

    def test_b1_single_file(self):
        self.same_as_cpython({"main.py": SINGLE})

    def test_b2_keyword_module(self):
        self.same_as_cpython({"main.py": KEYWORD_MAIN, "kwmod.py": KEYWORD_MOD})

    def test_b2_function_level_in_module(self):
        self.same_as_cpython({
            "main.py": "import m\nprint(m.run([1, 2, 2, 3]))\nprint(m.has(2), m.has(9))\n",
            "m.py": "def run(xs):\n    s = set()\n    a = s.add\n    for x in xs:\n        a(x)\n"
                    "    return sorted(s)\n\nhas = frozenset([1, 2]).__contains__\n"})

    def test_b3_user_name_wins(self):
        self.same_as_cpython({"main.py": "class Box:\n    def __init__(self):\n        self.add = 5\n"
                                         "b = Box()\nprint(b.add)\n"})
        self.refused({"main.py": "class Box:\n    def __init__(self):\n        self.add = 5\n"
                                 "a = set().add\nprint(a)\n"}, "write instead", ".add")

    def test_b4_unsupported_method_is_refused(self):
        self.refused({"main.py": "pop = {1: 2}.pop\nprint(pop(1))\n"}, "write instead", ".pop")

    def test_b5_module_init_failure_is_loud(self):
        self.write({"main.py": "print('start')\nimport m\nprint('never')\n",
                    "m.py": "print('init m')\nx = 1 // 0\n"})
        built, exe = self.build(False)
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.stdout.decode(), "start\ninit m\n")
        self.assertEqual(ran.returncode, 1)
        self.assertIn("division by zero", ran.stderr.decode())


if __name__ == "__main__":
    unittest.main()
