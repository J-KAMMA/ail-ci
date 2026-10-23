"""fuzz72: the general path's str.casefold() was ASCII-only and aborted on non-ASCII text.

Before, pyboxed2 emitted ail_meth_str_casefold(), which was just lower() and therefore raised
`AIL limit: str_lower_nonascii` for every non-ASCII code point: "Straße".casefold() printed
nothing where CPython prints "strasse".  The general path now uses the same full-Unicode
casefold table as the typed path, over its UTF-16 strings.

The program also keeps the surrounding Unicode str methods compared on both builds:
upper/lower of sharp s and Turkish i, len of combining characters, isdigit/isdecimal/isnumeric
on fullwidth digits, empty/huge/negative repeats, and casefold values reaching a call through an
argument, a list item, an attribute and a dict value.  A casefold call with an argument is still
refused by name, as CPython raises TypeError for it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASE_METHODS = r'''class Box:
    def __init__(self, v: str):
        self.v = v


def show(label: str, s: str) -> None:
    print(label, repr(s), len(s), len(s.upper()), len(s.lower()), len(s.casefold()))
    print(repr(s.upper()), repr(s.lower()), repr(s.casefold()))
    print(s.isdigit(), s.isdecimal(), s.isnumeric())
    print(s.upper() == s, s.lower() == s, s.casefold() == s.lower(), s.casefold() == s)


def main() -> None:
    cases: list[str] = ["", "Straße", "ẞ", "İstanbul", "ı", "I", "ΣΣ", "ΟΣ",
                        "A\u0301B\u0302", "１２３", "①", "٣", "K", "abc"]
    boxes: list[Box] = [Box(s) for s in cases]
    for i in range(len(cases)):
        show("list", cases[i])
        show("arg", boxes[i].v)
    d: dict[str, str] = {"sharp": "Straße", "turkish": "İstanbul", "digits": "１２３",
                         "combining": "A\u0301", "greek": "ΣΣ"}
    for k in ["sharp", "turkish", "digits", "combining", "greek"]:
        show("dict", d[k])
    for n in [-1, 0, 1, 3, 10000]:
        t: str = "A\u0301" * n
        print(n, len(t), len(t.upper()), len(t.lower()), len(t.casefold()))
    print([(s.casefold(), len(s.casefold())) for s in cases])
    print([s.casefold() == s.lower() for s in cases])
    print("done")


main()
'''

CASE_ARG = r'''print("Straße".casefold(1))
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


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class Fuzz72Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz72-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_casefold_unicode(self):
        self.check('casefold_unicode', CASE_METHODS)

    def test_casefold_with_an_argument_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz72-arg-') as directory:
            for general in (True, False):
                built = _build(directory, 'casefold_arg_%s' % ('g' if general else 'd'),
                               CASE_ARG, general)
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertNotIn('Traceback', built.stderr)
                self.assertIn('not in the subset: .casefold() with 1 positional arguments',
                              built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
