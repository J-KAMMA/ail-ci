r"""pre103: a single NUL byte is a format code, not the end of the spec.

`format(1, '\x00')` and `format('a', '\x00')` returned the value on both builds;
CPython raises `ValueError: Unknown format code '\x0' for object of type 'int'`
(and `... 'str'`).  A NUL after width/sign/grouping is the same code, while a
float keeps CPython's quirk of accepting the NUL as no type.  None and instances
still raise the TypeError naming the class.  The spec reaches format() through a
literal, an argument, a list item, an attribute and a dict value.

Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class Box:
    pass


class Holder:
    def __init__(self, value, spec):
        self.value = value
        self.spec = spec


def through(value, spec):
    return format(value, spec)


def main():
    specs = ['\x00']
    values = [1, 0, -5, 10 ** 18, True, False]
    for spec in ['\x00', '5\x00', '0\x00', '+\x00', ' \x00', '#\x00', ',\x00', 'z\x00', '<\x00']:
        for v in values:
            try:
                print('int', type(v).__name__, repr(spec), repr(format(v, spec)))
            except Exception as e:
                print('int', type(v).__name__, repr(spec), type(e).__name__, e)
    for spec in ['\x00', '5\x00', '<\x00']:
        for v in ('a', '', 'héllo', None, Box(), 1.5, -2.5):
            try:
                print('mixed', type(v).__name__, repr(spec), repr(format(v, spec)))
            except Exception as e:
                print('mixed', type(v).__name__, repr(spec), type(e).__name__, e)
    for spec in ['\x00', '5\x00', '+\x00', '<\x00', ',\x00', '_\x00', '0\x00']:
        for v in (1.5, -2.5, 0.0, 1234567.5):
            try:
                print('float', repr(spec), repr(format(v, spec)))
            except Exception as e:
                print('float', repr(spec), type(e).__name__, e)

    specs_list = ['\x00']
    values_list = [7, 'q', 1.75, None]
    values_dict = {'i': 8, 's': 'r', 'f': 2.5, 'n': None}
    box = Holder(9, '\x00')
    for label, v, spec in (
        ('arg-int', 6, '\x00'), ('arg-str', 'p', '\x00'), ('arg-float', 3.5, '\x00'),
        ('list-int', values_list[0], specs_list[0]), ('list-str', values_list[1], specs_list[0]),
        ('list-float', values_list[2], specs_list[0]), ('list-none', values_list[3], specs_list[0]),
        ('attr-int', box.value, box.spec), ('attr-box', Box(), box.spec),
        ('dict-int', values_dict['i'], specs_list[0]), ('dict-str', values_dict['s'], specs_list[0]),
        ('dict-float', values_dict['f'], specs_list[0]), ('dict-none', values_dict['n'], specs_list[0]),
    ):
        try:
            print(label, repr(through(v, spec)))
        except Exception as e:
            print(label, type(e).__name__, e)

    print('empty', repr(format(1, '')), repr(format('a', '')), repr(format(1.5, '')))


try:
    print('literal-int', repr(format(1, '\x00')))
except Exception as e:
    print('literal-int', type(e).__name__, e)
try:
    print('literal-str', repr(format('a', '\x00')))
except Exception as e:
    print('literal-str', type(e).__name__, e)
main()
'''


def cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build_and_run(directory, name, text, general):
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


class Pre103Tests(unittest.TestCase):
    def test_single_nul_format_code(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre103-') as directory:
            want, rc, err = cpython(directory, 'nul', PROGRAM)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                got, build_err = build_and_run(directory, 'nul_%s' % ('g' if general else 'd'),
                                               PROGRAM, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
