"""Differential fuzz round 84: str.split/rsplit/splitlines argument binding.

Found while probing text processing (word counts built with split and dict,
line-by-line handling, punctuation stripping):

* A keyword that CPython finds ALREADY filled by a positional was silently
  dropped: `"a,b".split(",", sep="-")` printed `['a', 'b']` where CPython
  raises, and the same happened for `rsplit` and for `maxsplit`
  (`"a,b,c".split(",", 1, maxsplit=2)`).
* `splitlines` read its positional `keepends` and ignored a second keyword:
  `"a\nb".splitlines(True, keepends=False)` printed `['a\\n', 'b']` where
  CPython raises.

They are compile-time refusals by name now, like expandtabs' own tabsize. The
valid keyword forms (sep=/maxsplit= in either order, only one of them,
keepends=) still match CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VALID_KWARGS = r'''def main() -> None:
    s: str = " a,b,c "
    m: int = 1
    print(s.split(sep=","))
    print(s.rsplit(sep=","))
    print(s.split(maxsplit=m))
    print(s.rsplit(maxsplit=m))
    print(s.split(maxsplit=0))
    print("a,b,c".split(maxsplit=1, sep=","))
    print("a,b,c".rsplit(maxsplit=1, sep=","))
    print("a,b,c".split(sep=",", maxsplit=1))
    print("a,b,c".rsplit(sep=",", maxsplit=1))
    t: str = "a\nb\rc"
    print(t.splitlines(keepends=True))
    print(t.splitlines(keepends=False))
    print(t.splitlines(keepends=1))
    print(t.splitlines(keepends=0))
    print(t.splitlines(True))
    print(t.splitlines(False))
    print("done")


main()
'''

DUP_SEP = r'''def main() -> None:
    print("a,b".split(",", sep="-"))
    print("unreachable")


main()
'''

DUP_SEP_R = r'''def main() -> None:
    print("a,b".rsplit(",", sep="-"))
    print("unreachable")


main()
'''

DUP_MAXSPLIT = r'''def main() -> None:
    print("a,b,c".split(",", 1, maxsplit=2))
    print("unreachable")


main()
'''

DUP_KEEPENDS = r'''def main() -> None:
    print("a\nb".splitlines(True, keepends=False))
    print("unreachable")


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


class Fuzz84Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz84-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def check_refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz84-') as directory:
            _, got_rc, err = _cpython(directory, slug, text)
            self.assertNotEqual(got_rc, 0, 'CPython was expected to raise:\n%s' % text)
            self.assertIn(b'TypeError', err, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(needle, build_err, 'general=%s\n%s' % (general, build_err))

    def test_valid_keyword_forms(self):
        self.check('valid_kwargs', VALID_KWARGS)

    def test_split_rejects_duplicate_sep(self):
        self.check_refused('dup_sep', DUP_SEP, "got multiple values for argument 'sep'")

    def test_rsplit_rejects_duplicate_sep(self):
        self.check_refused('dup_sep_r', DUP_SEP_R, "got multiple values for argument 'sep'")

    def test_split_rejects_duplicate_maxsplit(self):
        self.check_refused('dup_maxsplit', DUP_MAXSPLIT, "got multiple values for argument 'maxsplit'")

    def test_splitlines_rejects_duplicate_keepends(self):
        self.check_refused('dup_keepends', DUP_KEEPENDS, "got multiple values for argument 'keepends'")


if __name__ == '__main__':
    unittest.main()
