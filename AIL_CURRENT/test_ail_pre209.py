"""Pre-209: a nested `def` with a `bytearray(...)` default is named as a mutable default.

The fuzz94 review recorded that a `bytearray()` default only hit the generic "nested def with
default parameters" refusal, because the mutable-literal test used `ast.literal_eval`, which
cannot see a construction call (a bytearray has no literal form).  The helper now recognises a
`bytearray(...)` call, also inside a tuple/list/set/dict display, so both builds name the cause
as a mutable literal default.

Deeper-nested keyword calls stay refused by name, and mutable defaults of escaped (returned or
loop-built) nested defs, module-level functions, lambdas and immutable defaults still match
CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BYTEARRAY_DEFAULTS = {
    'empty': '''
def main():
    def f(x, acc=bytearray()):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'bytes_arg': '''
def main():
    def f(x, acc=bytearray(b"ab")):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'size': '''
def main():
    def f(x, acc=bytearray(3)):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'list_arg': '''
def main():
    def f(x, acc=bytearray([0, 255])):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'tuple': '''
def main():
    def f(x, acc=(bytearray(), 0)):
        acc[0].append(x)
        return bytes(acc[0])
    print(f(1), f(2))


main()
''',
    'list_container': '''
def main():
    def f(x, acc=[bytearray()]):
        acc[0].append(x)
        return bytes(acc[0])
    print(f(1), f(2))


main()
''',
    'dict_container': '''
def main():
    def f(x, acc={"buf": bytearray()}):
        acc["buf"].append(x)
        return bytes(acc["buf"])
    print(f(1), f(2))


main()
''',
    'outer_value': '''
def main():
    data = bytearray(b"xy")

    def f(x, acc=bytearray(data)):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'kwonly': '''
def main():
    def f(x, *, acc=bytearray()):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
}

MATCHING = {
    'module_level': '''
def f(x, acc=bytearray()):
    acc.append(x)
    return bytes(acc)


def main():
    print(f(1), f(2), f(3))


main()
''',
    'returned': '''
def main():
    def make():
        def f(x, acc=bytearray()):
            acc.append(x)
            return bytes(acc)
        return f
    g = make()
    print(g(1), g(2))


main()
''',
    'returned_list': '''
def main():
    def make():
        def middle():
            def f(x, acc=[]):
                acc.append(x)
                return list(acc)
            return f
        return middle()
    g = make()
    print(g(1), g(2))


main()
''',
    'loop_built': '''
def main():
    fs = []
    for i in range(2):
        def f(x, acc=bytearray()):
            acc.append(x + i)
            return bytes(acc)
        fs.append(f)
    print(fs[0](1), fs[0](2), fs[1](1), fs[1](2))


main()
''',
    'lambda': '''
def main():
    f = lambda x, acc=bytearray(): (acc.append(x), bytes(acc))[1]
    print(f(1), f(2))


main()
''',
    'immutable': '''
def f(x, acc=(1, 2), note="n"):
    return (x, acc, note)


def main():
    def g(x, n=10):
        return x + n
    print(f(3), f(4, note="q"), g(1), g(2, n=3))


main()
''',
}

DEEPER_KEYWORDS = '''
def main():
    def outer():
        def f(x, acc=[]):
            acc.append(x)
            return list(acc)
        return f(x=1)
    print(outer())


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general, run=True):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    if not run:
        return True, ''
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre209Tests(unittest.TestCase):
    def test_bytearray_defaults_are_refused_as_mutable_literals(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre209-') as directory:
            for slug, text in BYTEARRAY_DEFAULTS.items():
                want, want_rc, err = _cpython(directory, 'ba_' + slug, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, 'ba_%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNone(got, 'ba %s built (general=%s)\n%s' % (slug, general, build_err))
                    self.assertIn('mutable literal default', build_err, 'ba %s (general=%s)' % (slug, general))
                    self.assertIn('bytearray', build_err, 'ba %s (general=%s)' % (slug, general))

    def test_escaped_module_and_immutable_defaults_match(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre209-') as directory:
            for slug, text in MATCHING.items():
                want, want_rc, err = _cpython(directory, 'ok_' + slug, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, 'ok_%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, 'ok %s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), 'ok %s (general=%s)\n%s' % (slug, general, build_err))

    def test_deeper_nested_keyword_call_stays_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre209-') as directory:
            want, want_rc, err = _cpython(directory, 'deep_kw', DEEPER_KEYWORDS)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, build_err = _build_and_run(directory, 'deep_kw_%s' % ('g' if general else 'd'),
                                                  DEEPER_KEYWORDS, general, run=False)
                self.assertIsNone(built, 'deep_kw built (general=%s)' % general)
                self.assertIn('keyword arguments in a call through a function value', build_err,
                              'deep_kw (general=%s)' % general)


if __name__ == '__main__':
    unittest.main()
