"""Pre-243: CPython's full "Invalid format specifier" ValueError text.

A spec whose leftover text is longer than one type code is rejected by the
format-spec parser.  AIL raised a bare ``ValueError: Invalid format specifier``,
while CPython 3.12 inserts the whole spec as text and names the value's type:
``Invalid format specifier '<spec>' for object of type '<type>'`` (quotes,
control characters, a NUL and non-ASCII code points stay as written; there is no
repr escaping).  The spec may arrive as a literal, an argument, a list item, an
attribute or a dict value, and the value through the same routes.

Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class Holder:
    def __init__(self, value, spec):
        self.value = value
        self.spec = spec


def pick(value):
    return value


def through(value, spec):
    return format(value, spec)


def show(label, value, spec, apply=False):
    try:
        result = through(value, spec) if apply else format(value, spec)
        print(label, type(value).__name__, repr(spec), repr(result))
    except Exception as e:
        print(label, type(value).__name__, repr(spec), type(e).__name__, e)


def main():
    specs = ['=_8,q', '<7 \x7f', '+ q', ' <8 q', "='x'", '5q!',
             '=' + 'a' * 200, 'a\nb', 'a\\b', "a''b", 'a\x00b']
    values = [12, -7, 0, True, False, 1.5, -2.5, 'x', '']
    for spec in specs:
        for value in values:
            show('loop', value, spec)
    for spec in ['=_8,q', '+ q', '<7 \x7f']:
        show('literal', 7, spec)
        show('argument', pick(7), spec)
        show('list', [7, 8][0], spec)
        show('attribute', Holder(7, spec).value, spec)
        show('dict', {'v': 7}['v'], spec)
        show('spec-argument', 7, spec, True)
        show('spec-list', 7, ['x', spec][1], True)
        show('spec-dict', 7, {'s': spec}['s'], True)
        show('spec-attribute', 7, Holder(7, spec).spec, True)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
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


class Pre243Tests(unittest.TestCase):
    def test_invalid_format_specifier_names_spec_and_type(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre243-') as directory:
            want, want_rc, err = _cpython(directory, 'invalid_spec', PROGRAM)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, 'invalid_spec_%s' % ('g' if general else 'd'),
                                      PROGRAM, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
