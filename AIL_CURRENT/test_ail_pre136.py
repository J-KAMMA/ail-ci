"""pre136: round() defaults, None ndigits and huge negative ndigits.

CPython's round() calls a user __round__ with no second argument when ndigits is
omitted or None, so the method's own default applies.  The general path passed a
boxed None / 0 instead, and round(2.5, -10**6) overflowed the scale to infinity
and printed nan.  round(x, NoIndex()) must also name the ndigits class.  These
programs compare both builds with CPython, including values reaching ndigits
through an argument, a list item, an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ROUND_DEFAULTS = r'''G = -2.5
H = "ho"
class F:
    def __round__(self, n=1.5):
        return repr(n)
class S:
    def __round__(self, n="hi"):
        return repr(n)
class Neg:
    def __round__(self, n=-1):
        return repr(n)
class Expr:
    def __round__(self, n=1+2):
        return repr(n)
class One:
    def __round__(self):
        return 'one'
class Variadic:
    def __round__(self, *args, **kw):
        return repr((args, kw))
class Required:
    def __round__(self, n):
        return repr(n)
class Hoisted:
    def __round__(self, n=G):
        return repr(n)
class HoistedStr:
    def __round__(self, n=H):
        return repr(n)
class Sub(F):
    pass
class SubOne(One):
    pass


def run(name, o):
    for tag in ('none', 'explicit', 'two'):
        try:
            if tag == 'none':
                r = round(o)
            elif tag == 'explicit':
                r = round(o, None)
            else:
                r = round(o, 2)
            print(name, tag, r)
        except Exception as e:
            print(name, tag, type(e).__name__, e)


def main():
    run('F', F())
    run('S', S())
    run('Neg', Neg())
    run('Expr', Expr())
    run('One', One())
    run('Variadic', Variadic())
    run('Required', Required())
    run('Hoisted', Hoisted())
    run('HoistedStr', HoistedStr())
    run('Sub', Sub())
    run('SubOne', SubOne())
    print('ok')


main()
'''

ROUND_NEGDIGITS = r'''class Idx:
    def __index__(self):
        return -3
class NoIndex:
    pass
class Holder:
    def __init__(self, v):
        self.v = v


def show(tag, fn):
    try:
        print(tag, fn())
    except Exception as e:
        print(tag, type(e).__name__, e)


def main():
    vals = [None, True, False, 0, 2, -3, 1000000, -1000000, -400, -323, -324,
            -308, -309, 1.5, Idx(), NoIndex(), 'x']
    for i, v in enumerate(vals):
        show('f%d' % i, lambda v=v: round(2.5, v))
        show('i%d' % i, lambda v=v: round(12345, v))
    lst = vals
    d = {'a': -1000000, 'b': None, 'c': 2}
    h = Holder(-1000000)
    for i in (0, 7, 8, 15):
        show('l%d' % i, lambda i=i: round(2.5, lst[i]))
    show('d1', lambda: round(2.5, d['a']))
    show('d2', lambda: round(2.5, d['b']))
    show('d3', lambda: round(2.5, d['c']))
    show('h1', lambda: round(2.5, h.v))
    show('neg0', lambda: round(-2.5, -10**6))
    show('neg1', lambda: round(2.5, -10**6))
    show('huge', lambda: round(2.5, 10**6))


main()
'''

ROUND_REVIEW = r'''class FF:
    def __index__(self):
        return 2.0
class I:
    def __round__(self, n=1e400):
        return repr(n)
class J:
    def __round__(self, n=-1e400):
        return repr(n)
class FI:
    def __index__(self):
        return 10**30
class FN:
    def __index__(self):
        return -(10**30)
class FM:
    def __index__(self):
        return 10**20 * 10**20
class Unused:
    def __round__(self, n=1e400):
        return repr(n)


def show(tag, fn):
    try:
        print(tag, fn())
    except Exception as e:
        print(tag, type(e).__name__, e)


show('bad', lambda: round(2.5, FF()))
show('inf', lambda: round(I()))
show('infnone', lambda: round(I(), None))
show('ninf', lambda: round(J()))
show('ninfnone', lambda: round(J(), None))
show('big', lambda: round(2.5, FI()))
show('nbig', lambda: round(2.5, FN()))
show('nbigneg', lambda: round(-2.5, FN()))
show('mulbig', lambda: round(2.5, FM()))
show('intbig', lambda: round(12345, FM()))
print('ok')
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
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre136Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre136-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_round_defaults(self):
        self.check('round_defaults', ROUND_DEFAULTS)

    def test_round_negdigits(self):
        self.check('round_negdigits', ROUND_NEGDIGITS)

    def test_round_review(self):
        self.check('round_review', ROUND_REVIEW)


if __name__ == '__main__':
    unittest.main()
