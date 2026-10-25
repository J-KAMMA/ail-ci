"""pre255: a class-level constant built through a list item, attribute or dict value.

The pre227 review recorded that such a value keeps its checked int64 arithmetic in the class
body, so `N = 2**62; xs = [N]; class C: X = xs[0] * 4` stopped at run time with
``integer overflow`` where CPython keeps an unbounded int.  These routes are now refused by
name at compile time on both builds.  Arithmetic outside a class body, and a later method body,
are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'list_item': '''N = 2**62
xs = [N]
class C:
    X = xs[0] * 4
print(C.X)
''',
    'dict_value': '''N = 2**62
d = {"n": N}
class C:
    X = d["n"] * 4
print(C.X)
''',
    'attribute': '''N = 2**62
class Box:
    pass
box = Box()
box.n = N
class C:
    X = box.n * 4
print(C.X)
''',
    'in_range_list': '''N = 2**61
xs = [N]
class C:
    X = xs[0] * 2 - 1
print(C.X)
''',
    'empty_list': '''xs = []
class C:
    X = xs[0] * 4
print(C.X)
''',
    'nested_argument': '''def build(xs):
    class C:
        X = xs[0] * 4
    return C.X
print(build([1]))
''',
}

MATCHES = '''N = 2**61
xs = [N]


class Plain:
    X = 2**61 * 2 - 1
    Y = "a" * 3


class Method:
    def read(self, values):
        return values[0] * 4


class Deferred:
    handlers = [lambda values: values[0] * 4]
    table = {"f": lambda values: values[0] * 4}
    doubled = "abc".upper() * 2
    list_method = ["xyz"][0].upper() * 2


print(Plain.X, Plain.Y)
print(xs[0] * 2 - 1)
print(Method().read([1]))
print(Deferred.handlers[0]([2]))
print(Deferred.table["f"]([2]))
print(Deferred.doubled, Deferred.list_method)
'''

MESSAGE = 'class-level constant built through a list item, attribute or dict value'


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre255Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre255-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn(MESSAGE, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertNotIn('integer overflow', output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def test_class_constant_routes_are_refused(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)

    def test_unaffected_arithmetic_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre255-') as directory:
            want, want_rc, err = _cpython(directory, 'matches', MATCHES)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, 'matches_' + ('g' if general else 'd'),
                                      MATCHES, general)
                self.assertIsNotNone(got, '%s\n%s' % ('general' if general else 'default', build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s\n%s' % ('general' if general else 'default', build_err))


if __name__ == '__main__':
    unittest.main()
