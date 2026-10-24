"""Explicit None slice bounds against CPython 3.12 (pre-161).

`x[None:None:-1]` is `x[::-1]`: an explicit None bound is an omitted one.  Lowerings that decided
a bound was present from its AST node alone read the None's `.i` and sliced from 0, so a local
`x = 'abcde'` answered '' where CPython answers 'edcba'.  Literal None bounds are now normalized
away for every lowering; on pyboxed2 a bound that is None only at run time (through a variable, an
argument, a list item, an attribute or a dict value) is read once and its tag checked, so it too
means "omitted" (the v1 emitter keeps its base treatment).  str, list, tuple, bytes and bytearray
are covered, including empty and single-element sequences, negative bounds, repetition (a negative
step), and the slice being an independent copy.

Each program is built with the general path forced and with the default build; the typed-lowering
case also builds with AIL_NO_GENERAL=1, so the typed path itself must answer.  stdout, the exit
status and the last stderr line must equal CPython's.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    src = Path(directory) / (name + '_' + mode + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    elif mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), None


LITERALS = r'''class Box:
    pass


def rev(s):
    return s[None:None:-1]


def tail_rev(s):
    return s[3:None:-1]


def head_rev(s):
    return s[None:2:-1]


def main():
    b = Box()
    b.v = 'abcde'
    d = {'k': 'abcde'}
    xs = ['abcde']
    t = ('abcde',)
    samples = ['abcde', [0, 1, 2, 3, 4], ['a', 'b', 'c', 'd', 'e'], (0, 1, 2, 3, 4),
               b'abcde', bytearray(b'abcde'), '', [], [], (), b'', bytearray(),
               'a', [7], ['z'], (7,), b'x', bytearray(b'x')]
    for s in samples:
        print(repr(s[None:None:-1]))
        print(repr(s[3:None:-1]))
        print(repr(s[None:2:-1]))
        print(repr(s[None:None:2]))
        print(repr(s[None:None:-2]))
        print(repr(s[4:None:-1]))
        print(repr(s[None:0:-1]))
        print(repr(s[::None]))
        print(repr(s[None:None:None]))
        print(repr(s[1:None]))
        print(repr(s[None:1]))
        print(repr(s[-1:None:-1]))
        print(repr(s[None:-2:-1]))
    print(repr(rev('abcde')))
    print(repr(rev([0, 1, 2, 3, 4])))
    print(repr(rev(('a', 'b', 'c'))))
    print(repr(rev(b'abcde')))
    print(repr(tail_rev('abcde')))
    print(repr(head_rev('abcde')))
    print(repr(rev(b.v)))
    print(repr(rev(d['k'])))
    print(repr(rev(xs[0])))
    print(repr(rev(t[0])))
    a = [0, 1, 2, 3, 4]
    c = a[None:None:-1]
    a[0] = 99
    print(repr(a), repr(c))


main()
'''

SOURCES = r'''class Box:
    pass


def rev(s, lo, hi, step):
    return s[lo:hi:step]


def note(tag, value):
    print('eval', tag, value)
    return value


def main():
    n = None
    x = 'abcde'
    print(repr(x[n:None:-1]))
    print(repr(x[3:n:-1]))
    print(repr(x[n:n:-1]))
    print(repr(x[n:n:None]))
    print(repr(rev('abcde', None, None, -1)))
    print(repr(rev('abcde', 3, None, -1)))
    vals = [None]
    print(repr(x[vals[0]:None:-1]))
    b = Box()
    b.n = None
    print(repr(x[b.n:None:-1]))
    d = {'n': None}
    print(repr(x[d['n']:None:-1]))
    for s in ([0, 1, 2, 3, 4], (0, 1, 2, 3, 4), b'abcde', bytearray(b'abcde')):
        print(repr(s[n:n:-1]))
        print(repr(s[3:n:-1]))
        print(repr(s[n:n:None]))
    print(repr(x[note('lo', None):note('hi', None):note('st', -1)]))


main()
'''

TYPED = r'''def main():
    x = 'abcde'
    print(x[None:None:-1])
    print(x[3:None:-1])
    print(x[None:2:-1])
    print(x[::None])
    l = [0, 1, 2, 3, 4]
    print(l[None:None:-1])
    print(l[3:None:-1])
    print(l[None:None:2])
    print(sum(l[None:None:-1]))
    print(len(l[None:None:-1]))
    e = ''
    one = 'a'
    print(repr(e[None:None:-1]), repr(one[None:None:-1]))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class NoneSliceBounds(unittest.TestCase):
    def check(self, name, text, modes=('general', 'default')):
        with tempfile.TemporaryDirectory(prefix='ail-pre161-') as directory:
            want = _cpython(directory, name, text)
            for mode in modes:
                got, error = _build_run(directory, name, text, mode)
                self.assertIsNone(error, '%s %s: %s' % (name, mode, error))
                self.assertEqual(got, want, '%s %s' % (name, mode))

    def test_literal_none_bounds_across_types(self):
        self.check('literals', LITERALS)

    def test_runtime_none_from_variables_items_attrs_dicts_arguments(self):
        self.check('sources', SOURCES)

    def test_typed_lowering_alone(self):
        self.check('typed', TYPED, modes=('typed', 'general', 'default'))


if __name__ == '__main__':
    unittest.main()
