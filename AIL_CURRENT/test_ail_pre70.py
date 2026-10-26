"""pre70: a None separator arriving at run time must split on whitespace.

qtest2's reviewer recorded that ``sep=None`` passed through a variable, a list
item, a dict value or an attribute raised ``ValueError: empty separator`` on
both builds, where CPython splits on whitespace (``" a  b ".split(sep)`` is
``['a', 'b']``).  The emitter already accepted a run-time ``None`` (its ``sn``
argument check allows it); the runtime split helpers now treat it as the
whitespace mode, including the pooled ``x = recv.split(sep)`` path.  A non-str
non-None separator still raises CPython's ``TypeError`` and an empty string
separator still raises ``ValueError``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RUNTIME_NONE = r'''class Box:
    def __init__(self):
        self.sep = None


def split_with(sep, s):
    return s.split(sep), s.rsplit(sep)


def main():
    sep = None
    s = "  a\tb\nc  "
    print(s.split(sep), s.rsplit(sep))
    print(s.split(sep, 0), s.rsplit(sep, 0))
    print(s.split(sep, 1), s.rsplit(sep, 1))
    print(s.split(sep, -1), s.rsplit(sep, -2))
    print(s.split(sep, 100), s.rsplit(sep, 100))
    xs = [None]
    print(s.split(xs[0]), s.rsplit(xs[0]))
    d = {"sep": None}
    print(s.split(d["sep"]), s.rsplit(d["sep"]))
    print(split_with(Box().sep, s))
    print(split_with(None, s))
    for raw in ["", " ", "   ", "x", " x ", "\x1ca\x85b\xa0c"]:
        print(repr(raw), raw.split(sep), raw.rsplit(sep))
    print(s.split(None), s.rsplit(None))
    print("a b c".split(maxsplit=1), "a b c".rsplit(maxsplit=1))
    print("a b c".split(sep=None, maxsplit=0), "a b c".rsplit(sep=None, maxsplit=0))


main()
'''

ASSIGN_POOL = r'''def f(sep):
    x = "  a  b ".rsplit(sep)
    y = "  a  b ".split(sep)
    return x, y


def main():
    sep = None
    a = " a  b ".split(sep)
    b = " a  b ".rsplit(sep)
    xs = [None]
    c = " a  b ".split(xs[0])
    d = {"sep": None}
    e = " a  b ".split(d["sep"])
    print(a, b, c, e)
    print(f(None))


main()
'''

NON_STR = r'''def show(sep):
    try:
        print("a b".split(sep))
    except Exception as e:
        print(type(e).__name__, e)
    try:
        print("a b".rsplit(sep))
    except Exception as e:
        print(type(e).__name__, e)


def main():
    for sep in [3, 3.0, b" ", [" "]]:
        show(sep)


main()
'''

EMPTY_SEP = r'''def main():
    sep = ""
    for s in ["a b", "", " "]:
        try:
            s.split(sep)
        except Exception as e:
            print(repr(s), type(e).__name__, e)
        try:
            s.rsplit(sep)
        except Exception as e:
            print(repr(s), type(e).__name__, e)


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


class Pre70Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre70-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_none_separator_reaches_split(self):
        self.check('runtime_none', RUNTIME_NONE)

    def test_none_separator_pooled_assignment(self):
        self.check('assign_pool', ASSIGN_POOL)

    def test_non_str_separator_typeerror(self):
        self.check('non_str', NON_STR)

    def test_empty_string_separator_valueerror(self):
        self.check('empty_sep', EMPTY_SEP)


if __name__ == '__main__':
    unittest.main()
