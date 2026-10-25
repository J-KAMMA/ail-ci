"""Differential fuzz round 51: bytes/bytearray ljust/rjust/center fillchar=None.

A shared wrapper used None as the sentinel for an omitted fillchar, so an explicit
None was silently treated as the default space instead of raising CPython's TypeError.
The wrapper now uses a private sentinel, and explicit None is rejected by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILL_PROGRAM = r'''def show(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except TypeError as e:
        print(label, "TypeError", str(e))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    show("bl_none", lambda: b"abc".ljust(5, None))
    show("br_none", lambda: b"abc".rjust(5, None))
    show("bc_none", lambda: b"abc".center(5, None))
    show("bal_none", lambda: bytearray(b"abc").ljust(5, None))
    show("bar_none", lambda: bytearray(b"abc").rjust(5, None))
    show("bac_none", lambda: bytearray(b"abc").center(5, None))
    show("bl", lambda: b"abc".ljust(5))
    show("br", lambda: b"abc".rjust(5))
    show("bc", lambda: b"abc".center(6))
    show("bal", lambda: bytearray(b"abc").ljust(5))
    show("bar", lambda: bytearray(b"abc").rjust(5))
    show("bac", lambda: bytearray(b"abc").center(6))
    show("blv", lambda: b"abc".ljust(5, b"_"))
    show("brv", lambda: b"abc".rjust(6, bytearray(b"#")))
    show("bcv", lambda: bytearray(b"abc").center(7, b"#"))
    show("sl_none", lambda: "abc".ljust(5, None))
    show("sr_none", lambda: "abc".rjust(5, None))
    show("sc_none", lambda: "abc".center(5, None))
    show("sl", lambda: "abc".ljust(5))
    show("sr", lambda: "abc".rjust(5))
    show("sc", lambda: "abc".center(6))
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


class Fuzz51Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz51-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_bytes_fillchar_none(self):
        self.check('bytes_fillchar_none', FILL_PROGRAM)


if __name__ == '__main__':
    unittest.main()
