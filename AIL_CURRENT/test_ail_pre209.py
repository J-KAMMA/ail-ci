"""pre209: a nested `def` with a `bytearray(...)` default.

The accepted pre209 change proposed naming a `bytearray(...)` default as a mutable literal and
refusing it by name, because the surface at that time only matched the generic "nested def with
default parameters" refusal. This tree contains the pre141 fix, which evaluates every non-literal
default once at the `def` statement into a hidden local, including a `bytearray(...)` call and one
inside a tuple/list/set/dict display. That matches CPython (the object is shared between calls and
a negative count raises at def time), so a refusal would regress it. Both changes are kept: pre141's
evaluation stands, and this module re-applies pre209's cases as CPython-parity regressions.
Deeper-nested keyword calls stay refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
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
    'empty_containers': '''
def main():
    def f(a=bytearray(0), b=bytearray(b""), c=(bytearray(),), d=[bytearray()],
          e={"x": bytearray()}):
        a.append(1)
        b.append(2)
        c[0].append(3)
        d[0].append(4)
        e["x"].append(5)
        return (bytes(a), bytes(b), bytes(c[0]), bytes(d[0]), bytes(e["x"]))
    print(f())
    print(f())


main()
''',
    'kw_source': '''
def main():
    def f(x, acc=bytearray(source=b"ab")):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
''',
    'nested_tuple': '''
def main():
    def f(x, acc=((bytearray(),),)):
        acc[0][0].append(x)
        return bytes(acc[0][0])
    print(f(1), f(2))


main()
''',
    'class_default': '''
def main():
    def f(x, cls=bytearray):
        return (x, cls(b"ab"))
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
    'alias_bindings': '''
class Box:
    pass


def main():
    data = bytearray(b"q")
    xs = [data]
    box = Box()
    box.data = data
    table = {"k": data}

    def make(src):
        return src

    def f(a=make(data), b=xs[0], c=box.data, d=table["k"]):
        a.append(1)
        b.append(2)
        c.append(3)
        d.append(4)
        return (bytes(a), bytes(b), bytes(c), bytes(d))

    print(f())
    print(f())
    data.append(9)
    print(f())


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
    'recursive': '''
def main():
    def f(n, acc=bytearray()):
        acc.append(n)
        if n:
            return f(n - 1)
        return bytes(acc)
    print(f(3))


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

NEGATIVE_COUNT = '''
def main():
    def f(x, acc=bytearray(-1)):
        acc.append(x)
        return bytes(acc)
    print(f(1), f(2))


main()
'''

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
    def test_bytearray_defaults_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre209-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc, err = _cpython(directory, 'ba_' + slug, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, 'ba_%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, 'ba %s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), 'ba %s (general=%s)\n%s' % (slug, general, build_err))

    def test_negative_count_raises_at_def_time(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre209-') as directory:
            want, want_rc, err = _cpython(directory, 'neg', NEGATIVE_COUNT)
            self.assertNotEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'neg_%s' % ('g' if general else 'd'),
                                                NEGATIVE_COUNT, general)
                self.assertIsNotNone(got, 'neg (general=%s)\n%s' % (general, build_err))
                self.assertNotEqual(got[1], 0, 'neg (general=%s) exited 0' % general)
                self.assertEqual(got[0], want, 'neg (general=%s)\n%s' % (general, build_err))

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
