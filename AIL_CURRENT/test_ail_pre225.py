r"""pre225: grouping with an unrecognised type code names the grouping conflict.

The pre206 review recorded that `format(12, ',q')` and `format(12, ', ')` said
`Unknown format code 'q'` / `' '` where CPython raises
`ValueError: Cannot specify ',' with 'q'.` / `'\x20'.`  CPython checks the grouping against the
type before it reports an unknown type code (and before it looks at the value); it also escapes a
space type code as `\x20` in both messages.  The help names the conflict for int, bool, float and
str, through a literal, an argument, a list item, an attribute and a dict value.

The sign-plus-grouping difference on `str` is a separate, pre-existing one and is not exercised
here.

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


def through(value, spec):
    return format(value, spec)


def show(label, value, spec):
    try:
        print(label, repr(spec), 'OK', repr(format(value, spec)))
    except ValueError as e:
        print(label, repr(spec), 'ValueError', e)
    except TypeError as e:
        print(label, repr(spec), 'TypeError', e)


def main():
    bad = [',q', '_q', ', ', '_ ', ',a', ',Z', ',s', ',c', ',n', ',b', ',o', ',x', ',X',
           '_n', '_c', '_s', '010,q', '>10, ', '<5,_ ']
    values = [(1234, 'int'), (-1234, 'neg'), (0, 'zero'), (True, 'true'), (False, 'false'),
              (1.5, 'float'), (-2.5, 'negfloat'), ('x', 'str'), ('', 'emptystr')]
    for spec in bad:
        for value, name in values:
            show(name, value, spec)

    good = [',d', '_d', '_b', '_o', '_x', '_X', ',e', '_e', ',f', '_f', ',g', '_g', ',%',
            ',', '_', '']
    for spec in good:
        for value, name in [(1234567, 'gint'), (-1234567, 'gneg'), (True, 'gtrue'),
                            (1234567.5, 'gfloat'), ('abc', 'gstr')]:
            show('good', value, spec)

    for spec in ['\x00', ',\x00', '_\x00', ' ,\x00']:
        for value, name in [(1, 'nint'), (1.5, 'nfloat'), ('x', 'nstr')]:
            show('nul', value, spec)
    for spec in ['_,', ',_']:
        show('both', 1, spec)
    for spec in ['5 ', '5\x1f', '+5 ']:
        show('codespace', 12, spec)
        show('codespace-str', 'x', spec)

    specs = [',q', ', ', '_ ', ',b', '_n']
    values = [7, True, 2.5, 'z']
    for spec in specs:
        for value in values:
            try:
                print('arg', repr(spec), repr(through(value, spec)))
            except ValueError as e:
                print('arg', repr(spec), 'ValueError', e)

    vals = [9, False, 3.25, 's']
    spec_list = [',q', ', ', '_ ', ',b']
    d = {'i': 9, 'b': False, 'f': 3.25, 's': 's', 'spec': '_ '}
    box = Holder(9, ',q')
    box2 = Holder('s', ', ')
    keys = ['i', 'b', 'f', 's']
    for i in range(4):
        show('list', vals[i], spec_list[i])
        show('dict', d[keys[i]], d['spec'])
    show('attr', box.value, box.spec)
    show('attrs', box2.value, box2.spec)


for label, value, spec in [('literal-int', 12, ',q'), ('literal-space', 12, ', '),
                           ('literal-float', 1.5, '_ '), ('literal-str', 'x', ',q')]:
    try:
        print(label, repr(format(value, spec)))
    except ValueError as e:
        print(label, type(e).__name__, e)

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


class Pre225Tests(unittest.TestCase):
    def test_grouping_with_unrecognised_type(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre225-') as directory:
            want, rc, err = cpython(directory, 'group', PROGRAM)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                got, build_err = build_and_run(directory, 'group_%s' % ('g' if general else 'd'),
                                               PROGRAM, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
