"""Differential qtest 5: str.zfill / str.expandtabs and a side-effecting receiver.

Found with small programs compared against CPython on both builds: `_str_concat_flatten`
(pyboxed2.py) emitted its leaf expressions while it was still deciding whether to flatten.
For a two-leaf `a + b` string concat that did not qualify, the emitted code stayed and the
normal path evaluated both leaves again, so any side effect in either operand ran twice:

    i = [0]
    def nxt():
        i[0] += 1
        return i[0]
    print(repr(("-" + str(nxt())).zfill(nxt())))   # CPython '-1' 2, AIL '-02' 3

The plan is now built before anything is emitted.  The valid zfill / expandtabs shapes
(signs, empty strings, widths below the length, tab sizes 0/1/8, tabs after newlines) are
kept compared with CPython on both builds too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

AREA = r'''def main() -> None:
    strs = ["", "-", "+", "42", "-42", "+42", "abc", "-abc", " 7"]
    for s in strs:
        for w in [0, 1, 2, 3, 5, 6, -1]:
            print(repr(s.zfill(w)))
    tabs = ["", "\t", "a\tb", "\t\t", "\n\t", "\r\t", "a\tb\nc\td",
            "x\n\t\n\t", "12345678\t", "\t\n\t"]
    for s in tabs:
        for t in [0, 1, 8]:
            print(repr(s.expandtabs(t)))
        print(repr(s.expandtabs()))


main()
'''

SIDE_EFFECT = r'''i = [0]


def nxt():
    i[0] += 1
    return i[0]


def main() -> None:
    print(repr(("-" + str(nxt())).zfill(5)), i[0])
    i[0] = 0
    print(repr(("a\tb" + str(nxt())).expandtabs(4)), i[0])
    i[0] = 0
    print(repr(("-" + str(nxt()))), i[0])
    i[0] = 0
    print(repr("x" + str(nxt()) + "y"), i[0])
    i[0] = 0
    print(repr(("a" + str(nxt()) + "b" + str(nxt()))), i[0])


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Qtest5Tests(unittest.TestCase):
    def check_matches_cpython(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-qtest5-') as directory:
            want, code, err = _cpython(directory, name, text)
            self.assertEqual(code, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, code),
                                 got.stderr.decode('utf-8', 'replace')[-1500:])

    def test_zfill_expandtabs_match_cpython(self):
        self.check_matches_cpython('area', AREA)

    def test_side_effecting_concat_receiver_evaluated_once(self):
        self.check_matches_cpython('side_effect', SIDE_EFFECT)


if __name__ == '__main__':
    unittest.main()
