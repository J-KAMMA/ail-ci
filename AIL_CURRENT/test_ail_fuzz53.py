"""Fuzz round 53: min()/max() of an empty iterable used the Python 2 wording.

Found with the string-ordering probes: catching the ValueError from `min([])`, `max([])`,
`min("")`, `max("")`, `min({})` or `max(set())` printed

    ValueError min() arg is an empty sequence

where CPython 3.12 prints `min() iterable argument is empty` (and the max equivalent).  The
boxed/general emitter raised the old text directly; the typed and iterator paths already had
CPython's wording.  Defaults and key= still work, and a non-empty iterable still returns its
string min/max.

Each program is built in the default and AIL_UNIFIED_FORCE=1 general builds and must print
CPython's stdout with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EMPTY_MINMAX = r'''def main() -> None:
    xs: list[str] = []
    d: dict[str, int] = {}
    s: set[str] = set()
    for name, fn in [("min list", lambda: min(xs)), ("max list", lambda: max(xs)),
                     ("min str", lambda: min("")), ("max str", lambda: max("")),
                     ("min dict", lambda: min(d)), ("max dict", lambda: max(d)),
                     ("min set", lambda: min(s)), ("max set", lambda: max(s)),
                     ("min key", lambda: min(xs, key=lambda x: x)),
                     ("max key", lambda: max(xs, key=lambda x: x))]:
        try:
            print(name, fn())
        except ValueError as e:
            print(name, "ValueError", e)
    print(xs, min(xs, default="z"), max(xs, default="Z"))
    print(min("", default="z"), max("", default="Z"))
    words: list[str] = ["b", "A", "a", "B"]
    print(min(words), max(words), min(words, key=str.lower), max(words, key=str.lower))


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


class Fuzz53Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz53-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (False, True):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))
            return want

    def test_empty_min_max_message(self):
        out = self.check('empty_minmax', EMPTY_MINMAX)
        self.assertIn(b'ValueError min() iterable argument is empty', out)


if __name__ == '__main__':
    unittest.main()
