"""Differential round qtest4: bytes/bytearray center/ljust/rjust with a wrong-type fillchar.

The bytes wrappers turned every non-bytes fillchar into the generic `_ail_bs` error
("a bytes-like object is required, not 'int'"), while CPython raises
`center() argument 2 must be a byte string of length 1, not int`.  A non-bytes fill
whose width is narrower than the text was affected too: CPython still validates the
fill before it pads.  The str methods already matched CPython; they are kept here as
a control for widths smaller than the text, negative widths and multi-character fills.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BYTES_FILL_PROGRAM = r'''def show(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except TypeError as e:
        print(label, "TypeError", str(e))


def main() -> None:
    show("bl_int", lambda: b"abc".ljust(5, 7))
    show("br_bool", lambda: b"abc".rjust(5, True))
    show("bc_float", lambda: b"abc".center(5, 1.5))
    show("bl_str", lambda: b"abc".ljust(5, "x"))
    show("br_list", lambda: b"abc".rjust(5, [1]))
    show("bc_tuple", lambda: b"abc".center(5, (1,)))
    show("bl_dict", lambda: b"abc".ljust(5, {1: 2}))
    show("br_set", lambda: b"abc".rjust(5, {1}))
    show("bc_none", lambda: b"abc".center(5, None))
    show("bl_two", lambda: b"abc".ljust(5, b"xy"))
    show("br_two_ba", lambda: b"abc".rjust(5, bytearray(b"xy")))
    show("bc_empty", lambda: b"abc".center(5, b""))
    show("bal_int", lambda: bytearray(b"abc").ljust(5, 7))
    show("bar_none", lambda: bytearray(b"abc").rjust(5, None))
    show("bac_str", lambda: bytearray(b"abc").center(5, "x"))
    show("bl_small", lambda: b"abcdef".ljust(2, 7))
    show("br_neg", lambda: b"abc".rjust(-3, 7))
    show("bc_zero", lambda: b"".center(0, 7))
    show("bl_ok", lambda: b"abc".ljust(5, b"#"))
    show("br_ok", lambda: b"abc".rjust(6, bytearray(b"#")))
    show("bc_ok", lambda: bytearray(b"abc").center(7, b"#"))
    print("done")


main()
'''

STR_FILL_PROGRAM = r'''def show(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except TypeError as e:
        print(label, "TypeError", str(e))


def main() -> None:
    show("sl_int", lambda: "abc".ljust(5, 7))
    show("sr_none", lambda: "abc".rjust(5, None))
    show("sc_two", lambda: "abc".center(5, "xy"))
    show("sl_two", lambda: "abc".ljust(5, "xy"))
    show("sr_bool", lambda: "abc".rjust(5, True))
    show("sc_str", lambda: "abc".center(5, "x"))
    show("sl_neg", lambda: "abc".ljust(-3, "x"))
    show("sr_small", lambda: "abc".rjust(2, "x"))
    show("sc_empty", lambda: "".center(0, "x"))
    show("sc_uni", lambda: "aé".center(8, "日"))
    show("sl_uni", lambda: "日本語".ljust(7, "é"))
    show("sr_uni", lambda: "aé".rjust(4, "*"))
    show("sc_uni_odd", lambda: "abc".center(8, "é"))
    show("sc_uni_even", lambda: "abc".center(7, "é"))
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


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


class QTest4Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-qtest4-') as directory:
            want = _cpython(directory, slug, text)
            self.assertEqual(want.returncode, rc, want.stderr.decode('utf-8', 'replace'))
            expected = (want.stdout.replace(b'\r\n', b'\n'), rc)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, expected, '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_bytes_fillchar_wrong_type(self):
        self.check('bytes_fill_wrong', BYTES_FILL_PROGRAM)

    def test_str_fill_control(self):
        self.check('str_fill_control', STR_FILL_PROGRAM)


if __name__ == '__main__':
    unittest.main()
