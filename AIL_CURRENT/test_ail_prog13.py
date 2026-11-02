"""Typed reach for the hot functions of eight real programs (job-prog13, 2026-11-02), against CPython 3.12.

The census programs whose hot functions were still on the general path at the job's base were
`g12_026` (an Optional scalar return on a method, `Elevator.step() -> int | None`) and two programs
left as follow-ups (a generated enum table and a datetime value built at module scope).  The diff
this module covers lets a method carry an Optional scalar parameter or result, provided its name is
unique in the program, and lets a list comprehension over struct instances produce `list[str]`.

P1  `lab/census/programs/gdev/g12_026.py` builds on the typed path and matches CPython.
P2  a focused program with `int | None` method parameters/results builds typed and matches CPython.
P3  `str | None` / `float | None` method parameters/results do the same (a local reaches the
    parameter as None, not a bare `None` literal, which the Optional rewrite still refuses by name).
P4  a duplicate method name, a decorated Optional method, and an Optional method result used inline in
    a dict literal stay on the general path (refused by name) and still match CPython -- a half-lowered
    method that returns a pair must never reach the general build.
P5  `[p.name for p in ps]` over a dataclass list builds typed and matches CPython.
P6  the programs that already built typed at the base still do.
P7  an Optional method named like a builtin container method (`get`, `pop`) does not capture a dict /
    list call: such a program stays on the general path, and a call whose receiver is provably the user
    class still lowers.
P8  a class-scope function without a `self` parameter and an unbound `S.add(obj, k)` call both pass
    their Optional argument in the right position.  Another compiler pass still requires a receiver
    for a class-scope function, and the bool argument check assumes a bound method, so these two
    programs stay on the general path (correct output) rather than typing the affected method.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

OPT_INT = '''class Counter:
    def __init__(self, n: int) -> None:
        self.n = n
    def take(self, k: int) -> int | None:
        if self.n >= k:
            self.n -= k
            return self.n
        return None
    def add(self, v: int | None) -> int:
        if v is None:
            return self.n
        self.n += v
        return self.n


def main() -> None:
    c = Counter(5)
    r = c.take(2)
    if r is not None:
        print(r)
    missing = c.take(100)
    print(missing)
    a = c.add(0)
    b = c.add(3)
    t = c.take(0)
    print(a, b, t)


main()
'''

OPT_STR_FLOAT = '''class Box:
    def __init__(self) -> None:
        self.tag: int = 0
    def label(self, fallback: str | None) -> str | None:
        if fallback is None:
            return None
        return fallback + "!"
    def scale(self, base: float, k: float | None) -> float | None:
        if k is None:
            return None
        return base * k


def main() -> None:
    b = Box()
    x = b.label("hi")
    if x is not None:
        print(x)
    y = b.scale(2.0, 1.5)
    print(y)
    none: float | None = None
    z = b.scale(2.0, none)
    print(z)


main()
'''

DICT_OPTION = '''class Store:
    def __init__(self) -> None:
        self.n = 0
    def maybe(self, on: bool) -> int | None:
        if on:
            self.n += 1
            return self.n
        return None


def main() -> None:
    s = Store()
    d = {"a": s.maybe(True), "b": s.maybe(False)}
    print(d, s.n)


main()
'''

DUP_METHOD = '''class A:
    def value(self) -> int | None:
        return 1


class B:
    def value(self) -> int | None:
        return None


def main() -> None:
    print(A().value(), B().value())


main()
'''

DECORATED_METHOD = '''class C:
    @staticmethod
    def value() -> int | None:
        return 1


def main() -> None:
    print(C.value())


main()
'''

COLLIDE_GET = '''class Cache:
    def get(self, k: int | None) -> int | None:
        if k is None:
            return None
        return k


def main() -> None:
    c = Cache()
    d = {1: 10, 2: 20}
    print(c.get(3))
    print(d.get(1))
    print(d.get(9))


main()
'''

COLLIDE_POP = '''class Stack:
    def pop(self, k: int | None) -> int | None:
        if k is None:
            return None
        return k


def main() -> None:
    s = Stack()
    values = [1, 2, 3]
    print(s.pop(1))
    print(values.pop())
    print(values)


main()
'''

NO_SELF = '''class C:
    def value(x: int, k: int | None) -> int | None:
        if k is None:
            return x
        return x + k


def main() -> None:
    print(C.value(3, 4))
    none: int | None = None
    print(C.value(5, none))


main()
'''

UNBOUND = '''class S:
    def __init__(self, n: int) -> None:
        self.n = n

    def add(self, k: int | None) -> int:
        if k is None:
            return self.n
        self.n += k
        return self.n


def main() -> None:
    s = S(3)
    print(S.add(s, 4))
    print(s.n)


main()
'''

STRUCT_STR = '''from dataclasses import dataclass


@dataclass
class P:
    name: str
    n: int


def names(ps: list[P]) -> list[str]:
    return [p.name for p in ps]


def main() -> None:
    ps = [P("a", 1), P("b", 2)]
    out = names(ps)
    print(out, len(out), out[0], out[-1])
    print(names([]))


main()
'''

ALREADY_TYPED = {
    't140': (ROOT.parent / 'lab/corpus/programs/deepseek-v4.1-flash-free/t140.py',
             ROOT.parent / 'lab/corpus/tasks/t140/in2.txt'),
    't002': (ROOT.parent / 'lab/census/programs/dev/t002.py',
             ROOT.parent / 'lab/corpus/tasks/t002/in2.txt'),
    't001': (ROOT.parent / 'lab/corpus/programs/deepseek-v4.1-flash-free/t001.py',
             ROOT.parent / 'lab/corpus/tasks/t001/in2.txt'),
    'g06_000': (ROOT.parent / 'lab/census/programs/gdev/g06_000.py', None),
    't371': (ROOT.parent / 'lab/corpus/programs/deepseek-v4.1-flash-free/t371.py',
             ROOT.parent / 'lab/corpus/tasks/t371/in2.txt'),
}

G12_026 = ROOT.parent / 'lab/census/programs/gdev/g12_026.py'


def _env(extra=None):
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def compile_source(directory, source, name, extra_env=None):
    path = Path(directory, name + '.py')
    if isinstance(source, Path):
        path.write_bytes(source.read_bytes())
    else:
        path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + '_x')
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                          '-o', exe.name], cwd=directory, capture_output=True, text=True,
                         timeout=900, env=_env(extra_env))
    return res, exe, path


def run_python(path, stdin=b''):
    return subprocess.run([sys.executable, str(path)], input=stdin, capture_output=True, timeout=300)


def run_exe(exe, stdin=b''):
    return subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)


def typed(res):
    return 'built on the general path' not in res.stderr


def optlib_notes(source):
    sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
    import optlib
    notes = []
    optlib.rewrite(source, notes)
    return [text for _, text in notes]


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog13(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog13_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, source, name, expect_typed=True, stdin=b'', extra_env=None):
        res, exe, path = compile_source(self.tmp, source, name, extra_env)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertEqual(typed(res), expect_typed, res.stderr[-800:])
        want = run_python(path, stdin)
        got = run_exe(exe, stdin)
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return res, want

    def test_optional_int_method_typed(self):
        self.check(OPT_INT, 'opt_int')

    def test_optional_str_float_method_typed(self):
        self.check(OPT_STR_FLOAT, 'opt_str_float')

    def test_g12_026_typed_and_equal(self):
        if not G12_026.exists():
            self.skipTest('lab/census is not in this tree')
        self.check(G12_026, 'g12_026')

    def test_optional_method_result_in_a_dict_stays_general(self):
        _, want = self.check(DICT_OPTION, 'dict_option', expect_typed=False)
        self.assertTrue(any('returns an Optional' in n for n in optlib_notes(DICT_OPTION)))
        self.assertEqual(want.stdout, b"{'a': 1, 'b': None} 1\n")

    def test_duplicate_method_name_stays_general(self):
        self.check(DUP_METHOD, 'dup', expect_typed=False)
        self.assertTrue(any('not unique' in n for n in optlib_notes(DUP_METHOD)))

    def test_decorated_optional_method_stays_general(self):
        self.check(DECORATED_METHOD, 'decorated', expect_typed=False)
        self.assertTrue(any('decorated method' in n for n in optlib_notes(DECORATED_METHOD)))

    def test_struct_list_comprehension_of_str_typed(self):
        self.check(STRUCT_STR, 'struct_str')

    def test_optional_method_name_does_not_capture_builtin_get(self):
        _, want = self.check(COLLIDE_GET, 'collide_get', expect_typed=False)
        self.assertEqual(want.stdout, b'3\n10\nNone\n')
        self.assertTrue(any('builtin method' in n for n in optlib_notes(COLLIDE_GET)))

    def test_optional_method_name_does_not_capture_builtin_pop(self):
        _, want = self.check(COLLIDE_POP, 'collide_pop', expect_typed=False)
        self.assertEqual(want.stdout, b'1\n3\n[1, 2]\n')
        self.assertTrue(any('builtin method' in n for n in optlib_notes(COLLIDE_POP)))

    def test_optional_method_without_a_self_parameter_matches_python(self):
        _, want = self.check(NO_SELF, 'no_self', expect_typed=False)
        self.assertEqual(want.stdout, b'7\n5\n')

    def test_unbound_optional_method_call_matches_python(self):
        _, want = self.check(UNBOUND, 'unbound', expect_typed=False)
        self.assertEqual(want.stdout, b'7\n7\n')

    def test_newly_typed_functions_on_both_builds(self):
        for env in ({'AIL_IR': '0'}, {'AIL_IR': '1'}):
            self.check(OPT_INT, 'opt_int_ir' + env['AIL_IR'], extra_env=env)

    def test_already_typed_programs_stay_typed(self):
        for name, (path, input_path) in ALREADY_TYPED.items():
            if not path.exists():
                continue
            stdin = input_path.read_bytes() if input_path is not None and input_path.exists() else b''
            self.check(path, name, stdin=stdin)


if __name__ == '__main__':
    unittest.main()
