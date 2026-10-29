"""covtop1: three constructs that real programs use and the compiler refused, each compared with CPython
(stdout and exit code) in the default build and with AIL_UNIFIED_FORCE=1, plus the refusals that stay.

1. a function stored in a field and called through the instance: `step.action()` with `action: Callable`
   in a dataclass, or `self.check = check` in __init__ (the general build said "the method .action()
   (on a value of unknown static kind)"). CPython looks the instance table up first, so the stored value
   is called; a receiver without that field raises AttributeError.
2. a generator expression nested in another one where the inner is the only argument of str.join, list,
   tuple or sorted (`"\\n".join(" ".join(str(x) for x in row) for row in m)`): the inner one is read to
   the end by that call, so building it at the call is what CPython does. Inner sum/min/max/any/all/set
   stay refused: they can stop or fail part way and the eager build would differ.
3. refusals by name with file:line: `Class.__dataclass_fields__` (compiled, then failed at run time), and a
   module-level function defined twice (`@f.register def _(...)`), which used to say only "duplicate AIL name".
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FIELD_CALLS = r"""from dataclasses import dataclass
from typing import Callable


@dataclass
class Step:
    name: str
    action: Callable[[], int]


class Hook:
    def __init__(self, label, check):
        self.label = label
        self.check = check


def make(n):
    return lambda: n * 2


def helper(x):
    return x - 1


def main():
    steps = [Step("a", make(1)), Step("b", lambda: 7), Step("c", make(21))]
    total = 0
    for s in steps:
        v = s.action()
        total += v
        print(s.name, v)
    print(total)
    hooks = [Hook("x", lambda a: a + 1), Hook("y", lambda a: a * 3), Hook("z", helper)]
    for h in hooks:
        print(h.label, h.check(10))
    h0 = hooks[0]
    try:
        h0.check(1, 2)
    except TypeError as e:
        print("TypeError", e)
    other = [1, 2]
    try:
        other[0].action()
    except AttributeError as e:
        print("AttributeError", e)
    print(steps[2].action() + hooks[2].check(5))


main()
"""

NESTED_GENEXP = r"""def fmt(m):
    width = max(len(str(x)) for row in m for x in row)
    return "\n".join(" ".join(str(x).rjust(width) for x in row) for row in m)


def words(lines):
    return [",".join(w.upper() for w in ln.split()) for ln in lines]


def flat(m):
    return sorted(sum(row) for row in m)


def pairs(n):
    return ";".join(",".join(str(i * j) for j in range(1, n + 1)) for i in range(1, n + 1))


def lists(m):
    return " | ".join(str(list(x * 2 for x in row)) for row in m if len(list(x for x in row)) > 1)


def tuples(m):
    out = []
    for t in tuple(tuple(x + 1 for x in row) for row in m):
        out.append(t)
    return out


def sortedrows(m):
    return "/".join(" ".join(str(v) for v in sorted(x for x in row)) for row in m)


def anyrows(m):
    return any(" ".join(str(v) for v in row) == "3 2 1" for row in m)


def main():
    m = [[1, 22, 3], [4, 5, 66], [3, 2, 1]]
    print(fmt(m))
    print(words(["a b", "cd e f"]))
    print(flat(m))
    print(pairs(3))
    print(lists(m))
    print(tuples(m))
    print(sortedrows(m))
    print(anyrows(m), anyrows([[1]]))
    print(list(",".join(c for c in w) for w in ["xy", "z"]))


main()
"""

# the inner generator is consumed by something that can stop early or fail part way: stays refused
NESTED_SUM = r"""def main():
    m = [[1, 2], [3, 4]]
    print(max(sum(x for x in row) for row in m))


main()
"""

NESTED_ANY = r"""def main():
    m = [[1, 2], [3, 4]]
    print(list(any(x > 2 for x in row) for row in m))


main()
"""

DATACLASS_FIELDS = r"""from dataclasses import dataclass


@dataclass
class P:
    a: int
    b: str


def main():
    for f in P.__dataclass_fields__.values():
        print(f.name)


main()
"""

DUPLICATE_DEF = r"""from functools import singledispatch


@singledispatch
def show(v):
    return "other"


@show.register
def _(v: int):
    return "int"


@show.register
def _(v: str):
    return "str"


def main():
    print(show(1), show("a"), show(2.5))


main()
"""

UNKNOWN_METHOD = r"""class A:
    def __init__(self):
        self.go = lambda: 1


def main():
    a = A()
    print(a.go())
    print(a.nothing())


main()
"""

BOUND_METHOD_FIELD = r"""class Doubler:
    def __call__(self, x):
        return 2 * x


class Acc:
    def __init__(self):
        self.t = 0

    def add(self, x):
        self.t += x
        return self.t


class Box:
    def __init__(self, fn):
        self.fn = fn


acc = Acc()
for b in [Box(Doubler()), Box(acc.add), Box(len)]:
    try:
        print(b.fn(5))
    except TypeError as e:
        print("TE", e)
"""

BUILTIN_NAMED_FIELD = r"""class P:
    def __init__(self):
        self.upper = lambda: "field"


p = P()
print(p.upper())
"""

BUILTIN_BOUND_FIELD = r"""class Box:
    def __init__(self, fn):
        self.fn = fn


xs = []
b = Box(xs.append)
b.fn(1)
b.fn(2)
print(xs)
c = Box("abc".upper)
print(c.fn())
"""

FUNCTION_VALUES = r"""import math
from dataclasses import dataclass
from typing import Callable


def sq(x):
    return x * x


@dataclass
class Step:
    name: str
    action: Callable


steps = [Step("sq", sq), Step("sqrt", math.sqrt), Step("abs", abs)]
for s in steps:
    print(s.name, s.action(16))
"""

CASES = [('field_calls', FIELD_CALLS), ('nested_genexp', NESTED_GENEXP), ('function_values', FUNCTION_VALUES)]


def compile_program(directory, text, name, force):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=600, env=env)
    return built, exe


class CovTop1(unittest.TestCase):
    def compare(self, slug, text, force):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = compile_program(directory, text, slug, force)
            expected = subprocess.run([sys.executable, str(Path(directory, slug + '.py'))], capture_output=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def refused(self, slug, text, *needles, force=False):
        with tempfile.TemporaryDirectory() as directory:
            built, exe = compile_program(directory, text, slug, force)
            self.assertNotEqual(built.returncode, 0, 'should be refused')
            self.assertFalse(exe.exists())
            message = built.stdout + built.stderr
            for needle in needles:
                self.assertIn(needle, message)

    def test_default_build(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.compare(slug, text, False)

    def test_unified_force(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.compare(slug + '_force', text, True)

    def test_nested_sum_stays_refused(self):
        # (the default build keeps its typed lowering of this; the general build is what changed)
        self.refused('nested_sum', NESTED_SUM, 'nested inside another generator expression', force=True)

    def test_nested_any_stays_refused(self):
        self.refused('nested_any', NESTED_ANY, 'nested inside another generator expression', force=True)

    def test_dataclass_fields_refused_by_name(self):
        self.refused('dataclass_fields', DATACLASS_FIELDS, '__dataclass_fields__', 'dataclass_fields.py:11', 'write instead')

    def test_duplicate_def_has_line_and_hint(self):
        self.refused('duplicate_def', DUPLICATE_DEF, 'duplicate_def.py:15', 'duplicate AIL name: _', 'write instead')

    def test_field_with_bound_method_value_refused(self):
        # a bound method taken as a value (`acc.add`) is not modelled: refuse, do not crash at run time
        self.refused('bound_method_field', BOUND_METHOD_FIELD, '.fn()')
        self.refused('bound_method_field_force', BOUND_METHOD_FIELD, '.fn()', force=True)

    def test_field_with_builtin_bound_method_refused(self):
        self.refused('builtin_bound_field', BUILTIN_BOUND_FIELD, '.fn()')
        self.refused('builtin_bound_field_force', BUILTIN_BOUND_FIELD, '.fn()', force=True)

    def test_field_named_like_builtin_method_refused(self):
        self.refused('builtin_named_field', BUILTIN_NAMED_FIELD, 'builtin_named_field.py:3', 'write instead')
        self.refused('builtin_named_field_force', BUILTIN_NAMED_FIELD, 'write instead', force=True)

    def test_unknown_method_still_refused(self):
        self.refused('unknown_method', UNKNOWN_METHOD, '.nothing()')


if __name__ == '__main__':
    unittest.main()
