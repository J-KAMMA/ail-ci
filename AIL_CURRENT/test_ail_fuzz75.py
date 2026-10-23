"""Differential fuzz round 75: print's sep=/end= accept None as CPython's default.

Found with small programs compared against CPython on both builds:

On the general path `print("a", "b", sep=None)` wrote "ab" and
`print("a", "b", end=None)` dropped the newline, because the None's zero
payload was read as an empty str. CPython treats None as the default
separator " " / terminator "\\n". The same happened when the None reached
print through a variable, a function argument, a list item, a dict value or
an attribute. A non-str sep/end (int, float, bool, list) was also read as an
empty string and silently lost the separator/newline; CPython raises
TypeError "sep must be None or a string, not int".

The general runtime now normalises None to the default and raises CPython's
TypeError for any other non-str before writing a byte. The programs below keep
the literal, argument, list, dict and attribute shapes plus no-argument and
flush forms compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PRINT_NONE = r'''def main() -> None:
    print("a", "b", sep=None)
    print("a", "b", end=None)
    print("a", "b", sep=None, end=None)
    print("x", sep=None)
    print("y", end=None)
    print("done")


main()
'''

PRINT_NONE_SOURCES = r'''class C:
    pass


def show(sep, end) -> None:
    print("a", "b", sep=sep, end=end)


def main() -> None:
    s = None
    e = None
    show(s, e)
    xs = [None, "-", None]
    print("a", "b", sep=xs[0], end=xs[2])
    print("a", "b", sep=xs[1], end=xs[0])
    d = {"s": None, "e": None}
    print("a", "b", sep=d["s"], end=d["e"])
    c = C()
    c.sep = None
    c.end = None
    print("a", "b", sep=c.sep, end=c.end)
    print("done")


main()
'''

PRINT_WRONG_TYPES = r'''def main() -> None:
    for v in [5, 1.5, True, [1]]:
        try:
            print("a", "b", sep=v)
        except TypeError as e:
            print("sep TypeError", e)
        try:
            print("a", "b", end=v)
        except TypeError as e:
            print("end TypeError", e)
    print("done")


main()
'''

PRINT_NO_ARGS = r'''def main() -> None:
    print(sep=None)
    print(end=None)
    print(sep="-", end=None)
    print(*[], sep=None, end=None)
    print(*[], sep="-", end="!")
    print()
    print(end="")
    print("after")
    print("done")


main()
'''

PRINT_FLUSH = r'''import sys


def main() -> None:
    print("a", "b", sep=None, end=None, flush=True)
    print("c", flush=False)
    print("d", "e", sep="-", end="!\n", flush=True)
    print("to out", 1, file=sys.stdout)
    print("done")


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


class Fuzz75Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz75-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_print_sep_end_none_literal(self):
        self.check('print_none', PRINT_NONE)

    def test_print_sep_end_none_sources(self):
        self.check('print_none_sources', PRINT_NONE_SOURCES)

    def test_print_sep_end_wrong_types(self):
        self.check('print_wrong_types', PRINT_WRONG_TYPES)

    def test_print_no_arguments(self):
        self.check('print_no_args', PRINT_NO_ARGS)

    def test_print_flush(self):
        self.check('print_flush', PRINT_FLUSH)


if __name__ == '__main__':
    unittest.main()
