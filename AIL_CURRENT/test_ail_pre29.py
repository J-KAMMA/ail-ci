"""pre29: the invalid-format-specifier message names the spec and the object type.

`format('x', ' +5')` (and `'0+5'`, `'  .2s'`) raised `ValueError: Invalid format specifier`
without CPython's `'<spec>' for object of type 'str'` suffix.  The parser now builds the full
message for str, int, bool and float, and the object types (None, list, tuple, dict, ...) take
object.__format__'s `unsupported format string passed to <type>.__format__` before the spec is
parsed, as CPython does.  A single non-ASCII type character is reported as CPython's unknown
format code (`\\x..`); a longer invalid spec is reported with its own text.

Values reach format() as literals, parameters, list items, attributes and dict values.  Programs
are built with the general path forced and with the default build; stdout and the exit status
must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

INVALID = r'''def show(v, spec):
    try:
        print(repr(v), repr(spec), repr(format(v, spec)))
    except Exception as e:
        print(repr(v), repr(spec), type(e).__name__ + ': ' + str(e))


def main():
    for spec in [' +5', '0+5', '  .2s', '+ 5', '0 5']:
        show('x', spec)
        show(42, spec)
        show(True, spec)
        show(1.5, spec)
        show(None, spec)
        show([1, 2], spec)
        show((1, 2), spec)
        show({'a': 1}, spec)


main()
'''

SOURCES = r'''class Box:
    def __init__(self, v):
        self.v = v


def show(label, v, spec):
    try:
        print(label, repr(v), repr(spec), repr(format(v, spec)))
    except Exception as e:
        print(label, repr(v), repr(spec), type(e).__name__ + ': ' + str(e))


def main():
    d = {'s': 'xyz', 'i': 42, 'b': True, 'f': 1.5}
    xs = ['xyz', 42, True, 1.5]
    box = Box('xyz')
    for spec in [' +5', '0+5', '  .2s']:
        for key in ['s', 'i', 'b', 'f']:
            show('dict', d[key], spec)
        for i in range(4):
            show('list', xs[i], spec)
        show('attr', box.v, spec)
        show('arg', 'xyz', spec)


main()
'''

OBJECTS = r'''def show(v, spec):
    try:
        print(repr(v), repr(spec), repr(format(v, spec)))
    except Exception as e:
        print(repr(v), repr(spec), type(e).__name__ + ': ' + str(e))


def main():
    for spec in ['', '>5', ' +5', '0+5', '  .2s', 'q']:
        show(None, spec)
        show([1, 2], spec)
        show((1, 2), spec)
        show({'a': 1}, spec)


main()
'''

VALID = r'''def show(v, spec):
    try:
        print(repr(v), repr(spec), repr(format(v, spec)))
    except Exception as e:
        print(repr(v), repr(spec), type(e).__name__ + ': ' + str(e))


def main():
    for spec in ['', '>8', '<8', '^8', '08', '+8', '-8', '.2s', '8.2s', '*^9']:
        show('xy', spec)
    for spec in ['', '>8', '08', '+8', '-8', ' 8', 'd', 'n', 'b', 'o', 'x', 'X']:
        for v in [42, -7, True]:
            show(v, spec)
    for spec in ['', '>8', '08', '+8', '-8', ' 8', 'e', 'E', 'f', 'F', 'g', 'G', '%', '.3f', '.2e']:
        show(2.25, spec)


main()
'''

UNICODE = r'''def show(v, spec):
    try:
        print(repr(v), repr(spec), repr(format(v, spec)))
    except Exception as e:
        print(repr(v), repr(spec), type(e).__name__ + ': ' + str(e))


def main():
    for spec in ['é', '€', '日', 'ÿ', 'Ā', 'xé', '€€', 'é€', '日x', 'xé', '>é', 'é#', '0é']:
        show('x', spec)
        show(42, spec)
        show(True, spec)
        show(1.5, spec)
        show(None, spec)
        show([1], spec)


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
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre29Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre29-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_invalid_spec_messages(self):
        self.check('invalid_spec', INVALID)

    def test_sources(self):
        self.check('sources', SOURCES)

    def test_object_format_types(self):
        self.check('objects', OBJECTS)

    def test_valid_specs(self):
        self.check('valid_specs', VALID)

    def test_unicode_specs(self):
        self.check('unicode_specs', UNICODE)


if __name__ == '__main__':
    unittest.main()
