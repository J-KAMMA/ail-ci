"""format() of None / an instance without __format__: CPython's TypeError (job pre102).

The general runtime parsed the format spec before it looked at the value, so `format(None, ' +8')` and
`format(Box(1), ' +8')` raised `ValueError: Invalid format specifier` where CPython raises
`TypeError: unsupported format string passed to NoneType.__format__` (resp. `Box.__format__`).
`object.__format__` rejects a non-empty spec straight away; only str/int/bool/float parse it. The
program below also keeps a class with its own `__format__` (the dispatch still happens first), the
empty spec (`str(x)`) and values arriving through an argument, a list item, a dict value and an
attribute, plus f-string and str.format spellings. Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = '''
class Box:
    def __init__(self, v):
        self.v = v

    def __str__(self):
        return 'box'


class Holder:
    def __init__(self):
        self.n = None
        self.b = Box(1)


class Custom:
    def __format__(self, spec):
        return 'C[' + spec + ']'


def identity(x):
    return x


def via(x):
    return format(x, ' +8')


def via_f(x):
    return f'{x: +8}'


def via_sf(x):
    return '{: +8}'.format(x)


def show(label, f):
    try:
        print(label, repr(f()))
    except Exception as e:
        print(label, type(e).__name__, e)


def main():
    b = Box(1)
    h = Holder()
    xs = [None, b]
    d = {'none': None, 'box': b}
    show('none', lambda: format(None, ' +8'))
    show('none-arg', lambda: via(None))
    show('none-get', lambda: format(identity(None), ' +8'))
    show('none-item', lambda: format(xs[0], ' +8'))
    show('none-dict', lambda: format(d['none'], ' +8'))
    show('none-attr', lambda: format(h.n, ' +8'))
    show('none-fstr', lambda: f'{None: +8}')
    show('none-farg', lambda: via_f(None))
    show('none-strfmt', lambda: '{: +8}'.format(None))
    show('none-strfmtarg', lambda: via_sf(None))
    show('none-empty', lambda: format(None, ''))
    show('none-pad', lambda: format(None, '>8'))
    show('box', lambda: format(b, ' +8'))
    show('box-arg', lambda: via(b))
    show('box-get', lambda: format(identity(b), ' +8'))
    show('box-item', lambda: format(xs[1], ' +8'))
    show('box-dict', lambda: format(d['box'], ' +8'))
    show('box-attr', lambda: format(h.b, ' +8'))
    show('box-fstr', lambda: f'{b: +8}')
    show('box-strfmt', lambda: '{: +8}'.format(b))
    show('box-empty', lambda: format(b, ''))
    show('box-pad', lambda: format(b, '>8'))
    show('custom', lambda: format(Custom(), '>8'))
    show('custom-plus', lambda: format(Custom(), ' +8'))
    show('custom-empty', lambda: format(Custom(), ''))
    print(format(Custom(), '*^9'))
    for label, value in (('list', [1]), ('tuple', (1,)), ('dict', {'a': 1}), ('set', {1}), ('range', range(2))):
        show(label + '-plus', lambda value=value: format(value, ' +8'))
        show(label + '-pad', lambda value=value: format(value, '>8'))
        show(label + '-empty', lambda value=value: format(value, ''))
    show('int', lambda: format(5, '>8'))
    show('float', lambda: format(1.5, '>8'))
    show('str', lambda: format('a', '>3'))


main()
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


class Pre102Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre102-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_none_and_instance_without_format(self):
        self.check('none_instance_format', PROGRAM)


if __name__ == '__main__':
    unittest.main()
