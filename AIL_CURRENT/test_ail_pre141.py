"""Pre-existing difference from CPython recorded by the pre117 reviewer.

A nested `def` whose default was not a literal constant (a name, an expression, an attribute, a
list item, a dict value, a call) was refused by both builds; CPython evaluates such a default
once, when the `def` statement runs, and keeps that object between calls. The default is now
evaluated into a hidden local at the `def` statement, so reassigning the source name afterwards
does not change the default, a shared list stays shared, and an argument/list-item/dict-value/
attribute value keeps the value it had at the `def`. A recursive call inside the nested function
reads the hidden local from that function's own frame, so it sees the def-time value too. Literal
scalar and tuple defaults are still filled in at the call site. `**kwargs` and positional-only
parameters remain refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'local_and_expressions': '''
def make(x):
    print("make", x)
    return [x]


def main():
    x = 5
    def f(a=x, b=-x, c=x * 2, d=make(x)):
        return (a, b, c, d)
    x = 6
    print(f())
    print(f(1), f(c=7))
    print(f())


main()
''',
    'containers_mutated_after_def': '''
class C:
    def __init__(self):
        self.v = 42
        self.lst = [1]


def outer(xs, d, c):
    def f(a=xs[0], b=d["k"], v=c.v, shared=c.lst):
        shared.append(v)
        return (a, b, v, list(shared))
    xs[0] = 70
    d["k"] = 80
    c.v = 90
    return f


def main():
    xs = [7]
    d = {"k": 8}
    f = outer(xs, d, C())
    print(xs, d["k"])
    print(f())
    print(f())


main()
''',
    'shared_mutable_literals': '''
def main():
    def f(x, acc=[], seen=set(), d={}):
        acc.append(x)
        seen.add(x)
        d[x] = d.get(x, 0) + 1
        return (list(acc), len(seen), dict(d))

    print(f(1))
    print(f(2))
    print(f(1))
    xs = [1]
    def g(a=xs):
        return a
    xs = [2]
    print(g(), g())
    print(xs)


main()
''',
    'global_and_keywords': '''
X = 2


def main():
    global X
    x = 4
    def f(a=X, b=X + 1, *, k=x):
        return (a, b, k)
    X = 9
    x = 40
    print(f())
    print(f(1, b=2, k=3))
    print(f(7, 8, k=6))


main()
''',
    'loop_and_escape': '''
def make(base):
    def f(a=base):
        return a
    return f


def main():
    fs = []
    for i in range(3):
        base = i * 10
        def f(a=base):
            return a
        fs.append(f)
    print(fs[0](), fs[1](), fs[2]())
    print(make(11)(), make(12)(13))
    x = 3
    if x:
        def g(a=x):
            return a
    x = 30
    print(g())


main()
''',
    'boundaries': '''
def main():
    def f(a=-5, b=9223372036854775807, c=(), d=(1, 2), e="", g=-0.5, h=0):
        return (a, b, c, d, e, g, h)
    print(f())


main()
''',
    'recursive_defaults': '''
_ail_nndefault_0 = "global"


def main():
    base = "local"
    def f(n, a=base):
        if n:
            return f(n - 1)
        return a
    print(f(2))

    def g(n, acc=[], seen={}, d=bytearray()):
        acc.append(n)
        seen[n] = seen.get(n, 0) + 1
        d.extend(b"x")
        if n:
            return g(n - 1)
        return (list(acc), dict(seen), bytes(d))
    print(g(2))

    x = 5
    def h(n, *, k=x, a=[]):
        a.append(n)
        if n:
            return h(n - 1)
        return (k, list(a))
    print(h(2))
    x = 50
    print(h(1, k=7))


main()
''',
}

REFUSED = {
    'kwargs': '''
def main():
    def f(**kw):
        return kw
    print(f())
main()
''',
    'positional_only': '''
def main():
    def f(a, /):
        return a
    print(f(1))
main()
''',
}


def _run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre141Tests(unittest.TestCase):
    def test_nonliteral_nested_defaults_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre141-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc = _run_cpython(directory, slug, text)
                self.assertEqual(want_rc, 0, slug)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))

    def test_unsupported_nested_parameters_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre141-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNone(got, '%s (general=%s) built\n%s' % (slug, general, build_err))
                    self.assertIn('nested def f with **kwargs or positional-only parameters',
                                  build_err, slug)


if __name__ == '__main__':
    unittest.main()
