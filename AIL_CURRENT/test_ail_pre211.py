"""pre211: a module function called from a class method under a boxed `try` keeps the handler.

The reviewer of job rbpre171 recorded two differences.  A generator expression used as a
value (`gen = (shl(1, -1) for _ in range(1))`) is already refused by name on both builds, so
nothing changes there.  The other one still differed on the default build: `C.run` called
`shl(1, -1)` and `c.run()` sat in a module `try`, but pymix's call graph only recorded direct
`Name` calls from module-level functions.  It therefore saw no protected call site for `shl`
and attached a typed clone that bypassed the boxed handler (`ValueError` escaped, exit 1).
Class method bodies and their attribute call sites are now part of that graph, so the callee
stays boxed and both builds catch the exception like CPython.

Shift counts reach the method through a literal, an argument, a list item, an attribute, a
dict value and an alias; valid shifts, zero counts, a method-to-method chain and the other
named traps (division, subscript, dict key) are covered too, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''def shl(a, b):
    return a << b


def shr(a, b):
    return a >> b


def divide(a, b):
    return a // b


def pick(xs, i):
    return xs[i]


def lookup(d, k):
    return d[k]


def helper(a, b):
    return shl(a, b)


class Box:
    def __init__(self, n):
        self.n = n

    def left(self, a, b):
        return shl(a, b)

    def right(self, a, b):
        return shr(a, b)

    def literal(self):
        return shl(1, -1)

    def chain(self, a, b):
        return helper(a, b)

    def outer(self, a, b):
        return self.chain(a, b)

    def div(self, a, b):
        return divide(a, b)

    def item(self, xs, i):
        return pick(xs, i)

    def key(self, d, k):
        return lookup(d, k)


c = Box(-4)
xs = [2, -2, 0, 62]
d = {"a": 1, "b": -3}
n = -1
alias = n

try:
    print("const", c.left(1, -1))
except ValueError as e:
    print("const", type(e).__name__, repr(str(e)))
try:
    print("right", c.right(8, -1))
except ValueError as e:
    print("right", type(e).__name__, repr(str(e)))
try:
    print("arg", c.left(xs[0], xs[1]))
except ValueError as e:
    print("arg", type(e).__name__, repr(str(e)))
try:
    print("zero", c.left(xs[2], xs[1]))
except ValueError as e:
    print("zero", type(e).__name__, repr(str(e)))
try:
    print("attr-dict", c.left(d["a"], c.n))
except ValueError as e:
    print("attr-dict", type(e).__name__, repr(str(e)))
try:
    print("dict", c.left(d["a"], d["b"]))
except ValueError as e:
    print("dict", type(e).__name__, repr(str(e)))
try:
    print("alias", c.left(xs[0], alias))
except ValueError as e:
    print("alias", type(e).__name__, repr(str(e)))
try:
    print("valid-zero", c.left(4, 0))
except ValueError as e:
    print("valid-zero", type(e).__name__, repr(str(e)))
try:
    print("valid-large", c.left(1, xs[3]))
except ValueError as e:
    print("valid-large", type(e).__name__, repr(str(e)))
try:
    print("valid-right", c.right(1 << 62, xs[3]))
except ValueError as e:
    print("valid-right", type(e).__name__, repr(str(e)))
try:
    print("chain", c.outer(1, -1))
except ValueError as e:
    print("chain", type(e).__name__, repr(str(e)))
try:
    print("literal", c.literal())
except ValueError as e:
    print("literal", type(e).__name__, repr(str(e)))
try:
    print("div", c.div(1, 0))
except ZeroDivisionError as e:
    print("div", type(e).__name__, repr(str(e)))
try:
    print("item", c.item([1, 2], 5))
except IndexError as e:
    print("item", type(e).__name__, repr(str(e)))
try:
    print("key", c.key({"a": 1}, "b"))
except KeyError as e:
    print("key", type(e).__name__, repr(str(e)))
print("valid", c.div(6, 3), shl(1, 3))
'''

GENEXP = r'''def shl(a, b):
    return a << b


gen = (shl(1, -1) for _ in range(1))
try:
    for value in gen:
        print(value)
except ValueError as e:
    print("caught", type(e).__name__, repr(str(e)))
print("valid", [4, 8])
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _build_and_run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre211Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre211-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                tag = 'g' if general else 'd'
                got, err = _build_and_run(directory, '%s_%s' % (slug, tag), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_method_call_sites(self):
        self.check('method_call_sites', PROGRAM)

    def test_generator_expression_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre211-') as directory:
            for general in (True, False):
                tag = 'g' if general else 'd'
                built, _ = _build(directory, 'genexp_' + tag, GENEXP, general)
                text = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, 'general=%s accepted it' % general)
                self.assertIn('generator expression used as a value', text,
                              'general=%s\n%s' % (general, text[-2000:]))


if __name__ == '__main__':
    unittest.main()
