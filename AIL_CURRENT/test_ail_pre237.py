"""pre237: a method body and its call sites stay on the boxed path.

The first still-differing item in the pre211 review was ``p4_collide``: a module function
``run`` and a class method ``run`` share a name, and the method calls the shift helper ``shl``.
pymix only walked module-function bodies for its call graph, so ``shl`` was selected as a typed
clone whose ``ValueError`` bypassed the caller's boxed ``try`` on the default build.  Method
bodies (including duplicate method names across classes and a collision with a module function)
and ``obj.method()`` call sites now feed that graph, so the callee stays boxed and both builds
catch the exception like CPython.

Counts reach the helper through a literal, an argument, a list item, an attribute, a dict value
and an alias; zero and valid shifts, method-to-method chains, a method's own ``try`` and the
other named traps (division, subscript) are covered too, on both builds.
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


def run(a, b):
    return shl(a, b)


def divide(a, b):
    return a // b


def pick(xs, i):
    return xs[i]


class C:
    def __init__(self, n):
        self.n = n

    def run(self, a, b):
        return shl(a, b)

    def via_self(self, a, b):
        return self.run(a, b)

    def via_global(self, a, b):
        return run(a, b)

    def literal(self):
        return shl(1, -1)

    def div(self, a, b):
        return divide(a, b)

    def item(self, xs, i):
        return pick(xs, i)

    def own_try(self, a, b):
        try:
            return shl(a, b)
        except ValueError as e:
            return (type(e).__name__, repr(str(e)))


class D:
    def run(self, a, b):
        return a + b


class E:
    def run(self, a, b):
        return shl(a, b)


class Holder:
    def __init__(self, c):
        self.c = c


def via_argument(obj, a, b):
    try:
        print("argument", obj.run(a, b))
    except ValueError as e:
        print("argument", type(e).__name__, repr(str(e)))


def report(tag, fn):
    try:
        print(tag, fn())
    except (ValueError, ZeroDivisionError, IndexError, KeyError) as e:
        print(tag, type(e).__name__, repr(str(e)))


c = C(-3)
alias = c
objs = [c, D()]
mapping = {"c": c}
holder = Holder(c)
xs = [2, -2, 0, 62]
d = {"a": 1, "b": -3}

report("direct", lambda: c.run(1, -1))
report("alias", lambda: alias.run(xs[0], d["b"]))
report("list", lambda: objs[0].run(xs[0], xs[1]))
report("dict", lambda: mapping["c"].run(d["a"], c.n))
report("attribute", lambda: holder.c.run(d["a"], d["b"]))
report("literal", lambda: c.literal())
report("self", lambda: c.via_self(1, -1))
report("global", lambda: c.via_global(xs[0], alias.n))
report("duplicate", lambda: E().run(1, -1))
report("own-try", lambda: c.own_try(1, -1))
report("div", lambda: c.div(1, 0))
report("item", lambda: c.item([1, 2], 5))
via_argument(c, 1, -1)
via_argument(E(), xs[0], d["b"])
print("valid", c.run(4, 1), run(1, 3), D().run(4, 4), E().run(4, 1))
print("valid-zero", c.run(4, 0), c.via_self(8, 0))
print("valid-global", c.via_global(3, 2), c.own_try(3, 2))
'''

UNCAUGHT = r'''def shl(a, b):
    return a << b


def run(a, b):
    return shl(a, b)


class C:
    def run(self, a, b):
        return shl(a, b)


print(C().run(1, -1))
print("after")
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre237Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, stderr_last=None):
        with tempfile.TemporaryDirectory(prefix='ail-pre237-') as directory:
            want, want_rc, want_err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, rc, want_err.decode('utf-8', 'replace')[-1500:])
            if stderr_last is not None:
                lines = [line for line in want_err.decode('utf-8', 'replace').splitlines() if line.strip()]
                self.assertEqual(lines[-1], stderr_last)
            for general in (True, False):
                tag = 'g' if general else 'd'
                got, err = _build_and_run(directory, '%s_%s' % (slug, tag), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (slug, general, err))
                if stderr_last is not None:
                    lines = [line for line in err.splitlines() if line.strip()]
                    self.assertEqual(lines[-1], stderr_last, '%s (general=%s)' % (slug, general))

    def test_colliding_method_call_sites(self):
        self.check('colliding_method_call_sites', PROGRAM)

    def test_uncaught_method_shift_names_the_value_error(self):
        self.check('method_shift_uncaught', UNCAUGHT, rc=1, stderr_last='ValueError: negative shift count')


if __name__ == '__main__':
    unittest.main()
