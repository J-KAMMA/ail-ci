"""Differential fuzz round 43: str search type names in tuple prefixes.

A tuple passed to str.startswith/endswith may contain only str. When a tuple member
is a bytes object, both builds raised the right TypeError but printed the member's
generic runtime tag instead of its class name:

    "abc".startswith((b"a",))    printed "not instance"
    "abc".endswith((b"c",))      printed "not instance"

CPython prints "not bytes". The same tag also flattened every user-class member to
"instance". The checks now take the name from the member object, which is the
prelude bytes class or the user class, so the caught message matches CPython.
Valid tuples, short-circuiting before a later bad member, empty receivers and
windowed startswith/endswith are kept in the same program.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TUPLE_MEMBER_TYPE_NAMES = r'''class Marker:
    pass


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except TypeError as e:
        print(tag, str(e))


def main() -> None:
    s: str = "abc"
    probe("start-bytes-first", lambda: s.startswith((b"a", "a")))
    probe("start-bytes-after-match", lambda: s.startswith(("a", b"x")))
    probe("start-bytes-after-miss", lambda: s.startswith(("x", "y", b"z")))
    probe("end-bytes", lambda: s.endswith((b"c",)))
    probe("empty-bytes", lambda: "".startswith((b"a",)))
    probe("bytearray", lambda: s.startswith((bytearray(b"a"),)))
    probe("marker", lambda: s.startswith((Marker(),)))
    probe("marker-end", lambda: s.endswith((Marker(),)))
    probe("valid-tuple", lambda: s.startswith(("x", "ab")))
    probe("valid-window", lambda: s.endswith(("bc", "b"), 1, 3))
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


class Fuzz43Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz43-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_tuple_member_type_names(self):
        self.check('tuple_member_type_names', TUPLE_MEMBER_TYPE_NAMES)


if __name__ == '__main__':
    unittest.main()
