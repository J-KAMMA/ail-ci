"""str.partition / str.rpartition: non-str separators must raise CPython's TypeError.

The general-path helper checked `len(sep)` before `find(sep)`, so an int, float or None separator
died with `object of type 'int' has no len()` instead of `must be str, not int`.  The separator
reaches the call through a parameter, a list item, an attribute and a dict value in the program
below; empty, repeated and multi-character separators are covered too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAM = r'''def part(s, sep):
    return s.partition(sep)


def rpart(s, sep):
    return s.rpartition(sep)


class C:
    def __init__(self, sep):
        self.sep = sep
        self.s = "a-b"


def main():
    for s, sep in [("a-b-c", "-"), ("abc", "-"), ("", "-"), ("--", "-"), ("abc", "abc"),
                   ("abc", "abcd"), ("aaaa", "aa"), ("banana", "na")]:
        print(s.partition(sep), s.rpartition(sep))
    for s in ["abc", "", "x"]:
        for right in (0, 1):
            try:
                print(s.rpartition("") if right else s.partition(""))
            except ValueError as e:
                print(type(e).__name__, e)
    cases = [1, None, 2.5, -0, b"-", ["-"], {"-": 1}]
    for sep in cases:
        try:
            print(part("a-b", sep))
        except Exception as e:
            print(type(e).__name__, e)
        try:
            print(rpart("a-b", sep))
        except Exception as e:
            print(type(e).__name__, e)
    for sep in cases:
        try:
            print([("a-b", sep)][0][0].partition(sep))
        except Exception as e:
            print(type(e).__name__, e)
    for sep in cases:
        try:
            c = C(sep)
            print(c.s.partition(c.sep))
        except Exception as e:
            print(type(e).__name__, e)
    for sep in cases:
        try:
            d = {"sep": sep}
            print("a-b".rpartition(d["sep"]))
        except Exception as e:
            print(type(e).__name__, e)
    print(("x" * 100000).partition("x" * 99999)[1] == "x" * 99999)
    print(("abc" * 3).rpartition("bc"))


main()
'''


def build_run(directory, text, general):
    src = Path(directory) / ('q3_g.py' if general else 'q3_d.py')
    exe = Path(directory) / ('q3_g' if general else 'q3_d')
    src.write_text(text, encoding='utf-8')
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
        return None, built.stdout + built.stderr
    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')


class QTest3(unittest.TestCase):
    def check(self, general):
        with tempfile.TemporaryDirectory(prefix='ail-qtest3-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', PROGRAM], capture_output=True, timeout=120)
            got, err = build_run(directory, PROGRAM, general)
            self.assertIsNotNone(got, err)
            self.assertEqual(got, (want.stdout.replace(b'\r\n', b'\n'), want.returncode), err)

    def test_partition_general(self):
        self.check(True)

    def test_partition_default(self):
        self.check(False)


if __name__ == '__main__':
    unittest.main()
