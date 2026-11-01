"""Python-syntax sources reaching the typed path: sys.argv elements and Optional helper returns.

P1  `sys.argv[i]` is a str, so it satisfies a parameter used with a str method (and a generated
    regex helper) instead of the caller defaulting that parameter to int.
P2  an unannotated helper that always returns one scalar kind is known not to return None, so its
    result can be assigned to a variable the Optional lowering has made a (flag, value) pair.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

ARGV_STR = '''import sys

def has_hi(s):
    return s.startswith("hi")

def main():
    if has_hi(sys.argv[1]):
        sys.stdout.write("yes\\n")
    else:
        sys.stdout.write("no\\n")

main()
'''

OPTIONAL_HELPER = '''import sys

def pack(d: int):
    return d + 1

def unpack(d: int) -> int | None:
    if d < 2:
        return None
    return d - 1

def main():
    data = int(sys.argv[1])
    res = pack(data)
    if data > 5:
        res = unpack(data)
    if res is None:
        sys.stdout.write("none\\n")
    else:
        sys.stdout.write("%d\\n" % res)

main()
'''


def build(tmp, name, text):
    source = Path(tmp) / (name + '.py')
    source.write_text(text, encoding='utf8')
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                             '--strict', '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, *args):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=60)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class TypedReach(unittest.TestCase):
    def test_argv_element_is_a_str(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'argv_str', ARGV_STR)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe, 'hi').stdout, 'yes\n')
            self.assertEqual(run(exe, 'no').stdout, 'no\n')

    def test_plain_helper_return_is_known_not_none(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'optional_helper', OPTIONAL_HELPER)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe, '3').stdout, '4\n')
            self.assertEqual(run(exe, '9').stdout, '8\n')


if __name__ == '__main__':
    unittest.main()
