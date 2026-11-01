"""Keyword-argument reach (docs/design/KWARGS_REACH.md, 2026-11-01), against CPython 3.12.

The general path used to refuse a call that passes a mapping with `**`.  It now expands the
mapping at run time and binds the callee with CPython's rules; required keyword-only parameters
are registered too.  The typed path is unchanged, so the default build falls back to the general
path for a program with `**`.

K1  keyword calls (defaults, required keyword-only, *args, **kwargs) match CPython
K2  `**mapping` direct, literal, mixed, multiple, forwarded and read from a value matches CPython
K3  methods and constructors take `**mapping`
K4  duplicate / unknown / missing / non-string / non-mapping / positional-only / surplus raise
    TypeError at the call (stdout and exit code match CPython)
K5  `*args` with `**`, and `**` to a builtin, are still refused by name
K6  the default build falls back to the general path for `**`; programs without `**` are untouched
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

BASIC = '''def f(a: int, b: int = 5, c: int = 7) -> int:
    return a * 100 + b * 10 + c

def g(a: int, *, b: int, c: int = 3) -> int:
    return a * 100 + b * 10 + c

def h(*args: int, **kw: int) -> int:
    return sum(args) * 1000 + sum(kw.values())

def main():
    print(f(b=2, a=1), f(1, c=3), f(a=4, c=5))
    print(g(1, b=2), g(1, c=4, b=5), g(a=6, b=7))
    print(h(), h(1, 2), h(a=1, b=2), h(1, 2, c=3))

main()
'''

UNPACK = '''def f(a: int, b: int = 5, c: int = 7) -> int:
    return a * 100 + b * 10 + c

def inner(**kw: int) -> int:
    return kw["a"] * 10 + kw["b"]

def wrapper(**kw: int) -> int:
    return inner(**kw)

def main():
    d = {"a": 1, "b": 2}
    print(f(**d))
    print(f(**{"a": 3, "c": 4}))
    print(f(9, **{"b": 8}))
    print(f(**{"a": 1}, **{"b": 2, "c": 3}))
    print(f(**{"a": 1, "b": 2}, c=4))
    print(f(c=6, **{"a": 1, "b": 2}))
    print(f(**{}, a=5))
    print(wrapper(a=1, b=2), wrapper(b=4, a=3))

main()
'''

DYNAMIC = '''class Box:
    def __init__(self, d: dict[str, int]) -> None:
        self.d = d

def f(a: int, b: int = 5, c: int = 7) -> int:
    return a * 100 + b * 10 + c

def use(d: dict[str, int]) -> int:
    return f(**d)

def main():
    d = {"a": 1, "b": 2}
    print(use(d))
    ds = [{"a": 3, "c": 4}]
    print(f(**ds[0]))
    box = Box({"a": 5, "b": 6})
    print(f(**box.d))
    m = {"k": {"a": 7, "c": 8}}
    print(f(**m["k"]))
    alias = d
    print(f(**alias))
    alias["b"] = 9
    print(f(**d))

main()
'''

METHOD = '''class C:
    def __init__(self, v: int, w: int = 1) -> None:
        self.v = v
        self.w = w

    def add(self, x: int, y: int = 2) -> int:
        return self.v * 100 + self.w * 10 + x + y

def main():
    c0 = C(**{"v": 3})
    print(c0.v, c0.w)
    print(C(**{"v": 3, "w": 4}).add(**{"x": 5}))
    c = C(7)
    print(c.add(**{"x": 1, "y": 3}))
    print(c.add(4, **{"y": 6}))
    d = {"x": 8, "y": 9}
    print(c.add(**d))

main()
'''

ORDER = '''def note(x: int) -> int:
    print("eval", x)
    return x

def f(a: int, b: int, *, c: int = 0) -> int:
    return a * 100 + b * 10 + c

def show(**kw: int) -> None:
    print(list(kw.keys()), list(kw.values()))

def main():
    print(f(note(1), **{"b": note(2)}, c=note(3)))
    show(**{"a": 1}, b=2, **{"c": 3})
    show(x=1, **{"y": 2})

main()
'''

ERRORS = {
    'dup_across_mappings': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(**{"a": 1}, **{"a": 2}))

main()
''',
    'dup_explicit_after': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(**{"a": 1}, a=2))

main()
''',
    'dup_explicit_before': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(a=1, **{"a": 2}))

main()
''',
    'unknown': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(**{"a": 1, "z": 2}))

main()
''',
    'missing': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(**{"z": 2}))

main()
''',
    'non_string_key': '''def h(**kw: int) -> int:
    return len(kw)

def main():
    print("before")
    print(h(**{1: 2}))

main()
''',
    'non_mapping': '''def h(**kw: int) -> int:
    return len(kw)

def main():
    print("before")
    print(h(**3))

main()
''',
    'positional_only_by_name': '''def g(a: int, /, b: int) -> int:
    return a * 10 + b

def main():
    print("before")
    print(g(**{"a": 1, "b": 2}))

main()
''',
    'duplicate_positional_and_keyword': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print("before")
    print(f(1, **{"a": 2}))

main()
''',
    'surplus_positional': '''def f(a: int) -> int:
    return a

def main():
    print("before")
    print(f(1, 2, **{}))

main()
''',
    'missing_required_keyword_only': '''def g(a: int, *, b: int) -> int:
    return a * 10 + b

def main():
    print("before")
    print(g(1, **{}))

main()
''',
}

REFUSALS = {
    'star_and_starstar': '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    xs = [1]
    d = {"b": 2}
    print(f(*xs, **d))

main()
''',
    'starstar_to_builtin': '''def main():
    d = {"a": 1}
    print(**d)

main()
''',
}


def compile_prog(directory, text, name, general):
    work = Path(tempfile.mkdtemp(dir=directory, prefix=name + '_'))
    source, exe = work / 'prog.py', work / 'exe'
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                          '--syntax', 'python', '-o', exe.name, '--debug-dir', 'dbg'],
                         cwd=work, capture_output=True, text=True, timeout=900, env=env)
    c_file = work / 'dbg' / 'program.c'
    return res, exe, (c_file.read_text(encoding='utf-8', errors='replace') if c_file.exists() else '')


def run_cpython(directory, text, name):
    work = Path(tempfile.mkdtemp(dir=directory, prefix=name + '_cp_'))
    source = work / 'prog.py'
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=300, encoding='utf-8')


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class KwargsReach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='kwargs_reach_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build_and_compare(self, text, name, general=True):
        res, exe, c_text = compile_prog(self.tmp, text, name, general)
        self.assertEqual(res.returncode, 0, name + ': ' + res.stderr[-1500:])
        want = run_cpython(self.tmp, text, name)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        if want.returncode != 0:
            self.assertTrue(got.stderr.strip(), name)
        return res, c_text, want

    def test_keyword_calls(self):
        for name, text in (('basic', BASIC), ('order', ORDER)):
            with self.subTest(name=name):
                self.build_and_compare(text, name)

    def test_star_star_calls(self):
        for name, text in (('unpack', UNPACK), ('dynamic', DYNAMIC), ('method', METHOD)):
            with self.subTest(name=name):
                self.build_and_compare(text, name)

    def test_star_star_errors(self):
        for name, text in ERRORS.items():
            with self.subTest(name=name):
                _, _, want = self.build_and_compare(text, name)
                self.assertNotEqual(want.returncode, 0, name)

    def test_refused_by_name(self):
        for name, text in REFUSALS.items():
            with self.subTest(name=name):
                res, _, _ = compile_prog(self.tmp, text, name, True)
                self.assertNotEqual(res.returncode, 0, name)
                self.assertIn('not in the subset', res.stderr, name)
                self.assertIn('**kwargs', res.stderr, name)

    def test_default_build_falls_back_for_star_star(self):
        res, _, _ = compile_prog(self.tmp, UNPACK, 'fallback', False)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertIn('built on the general path', res.stderr)

    def test_no_star_star_stays_on_the_old_path(self):
        text = '''def f(a: int, b: int = 2) -> int:
    return a * 10 + b

def main():
    print(f(1), f(a=3), f(4, b=5))

main()
'''
        _, c_text, _ = self.build_and_compare(text, 'plain')
        self.assertNotIn('argument after ** must be a mapping', c_text)
        self.assertNotIn('keywords must be strings', c_text)
        self.assertNotIn('got multiple values for keyword', c_text)


if __name__ == '__main__':
    unittest.main()
