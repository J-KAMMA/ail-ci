"""pre128: a __trunc__-only class is not a number for printf-style integer formatting.

CPython's `%d` / `%i` / `%u` ask for `__int__` then `__index__`; `__trunc__` is a
fallback of `int()`, not of `%`-formatting.  On both builds a class that only
defines `__trunc__` printed 5 for `%d` (and for every width/sign spelling), while
CPython raises `TypeError`.  The general-path percent formatter no longer falls
back to `__trunc__` for the decimal directives.  `__int__` and `__index__` keep
working, and the same check is made for a value reaching the format through a
function argument, a list item, an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TRUNC_PERCENT = r'''class TruncOnly:
    def __trunc__(self):
        return 5


class IntOnly:
    def __int__(self):
        return 6


class IndexOnly:
    def __index__(self):
        return 7


class IntAndTrunc:
    def __int__(self):
        return 9

    def __trunc__(self):
        return 5


class Box:
    def __init__(self, v):
        self.v = v


def probe(v):
    out = []
    try:
        out.append(repr('%d' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%i' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%u' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%x' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%o' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%f' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%c' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%5d' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%-5d' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%05d' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('%+d' % v))
    except TypeError:
        out.append('TypeError')
    try:
        out.append(repr('% d' % v))
    except TypeError:
        out.append('TypeError')
    return out


def main():
    print('trunc', probe(TruncOnly()))
    print('int', probe(IntOnly()))
    print('index', probe(IndexOnly()))
    print('both', probe(IntAndTrunc()))
    print('list', probe([TruncOnly()][0]))
    box = Box(TruncOnly())
    print('attr', probe(box.v))
    data = {'t': TruncOnly(), 'i': IntOnly(), 'x': IndexOnly()}
    print('dict', probe(data['t']), probe(data['i']), probe(data['x']))
    try:
        print('tuple', repr('%d %i %x' % (TruncOnly(), IntOnly(), IndexOnly())))
    except TypeError:
        print('tuple', 'TypeError')
    alias = TruncOnly()
    print('alias', probe(alias), alias.__trunc__())


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


class Pre128Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre128-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_trunc_only_percent(self):
        self.check('trunc_percent', TRUNC_PERCENT)


if __name__ == '__main__':
    unittest.main()
