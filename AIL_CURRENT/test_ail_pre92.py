"""CRLF and mixed line endings in a Python source file (job-pre92-10242042).

The SDK suite file `python/pkg-v12/test_all.py` was left with a mix of CRLF and LF lines: 65 lines
had been rewritten with LF while the other 940 kept CRLF, so a diff of the file carried 134 lines
of line-ending churn around a 6+/4- content change.  That churn is cosmetic, but a source file
whose lines agree on their terminator is easier to diff and to keep pinned.

The second check is the behaviour behind it: CRLF and mixed-ending source must mean exactly what
CPython says.  AIL normalises the source before parsing, and a triple-quoted string that spans a
physical CRLF is normalised by CPython's tokenizer too, so the two builds must agree with CPython
on the value and the exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
SDK_TEST_ALL = ROOT / 'python' / 'pkg-v12' / 'test_all.py'

PROGRAMS = {
    'all_crlf': (
        b'def total(xs):\r\n'
        b'    n = 0\r\n'
        b'    for v in xs:\r\n'
        b'        n += v\r\n'
        b'    return n\r\n'
        b'\r\n'
        b'print(total([1, 2, 3]))\r\n'
        b'print(sorted({"b": 2, "a": 1}.items()))\r\n'
    ),
    'mixed_endings': (
        b's = """alpha\r\n'
        b'beta\r\n'
        b'gamma"""\r\n'
        b'def total(xs):\n'
        b'    n = 0\n'
        b'    for v in xs:\n'
        b'        n += v\n'
        b'    return n\r\n'
        b'\r\n'
        b'print(total([4, 5]), len(s), repr(s), s.count("\\n"))\r\n'
    ),
}


def build(directory, name, data, general):
    src = Path(directory) / (name + '.ail')
    src.write_bytes(data)
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run(
        [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
         '-o', exe.name],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, done


class Pre92LineEndings(unittest.TestCase):
    def test_sdk_test_all_has_no_mixed_line_endings(self):
        data = SDK_TEST_ALL.read_bytes()
        crlf = data.count(b'\r\n')
        lf = data.count(b'\n') - crlf
        cr = data.count(b'\r') - crlf
        self.assertTrue(crlf, 'test_all.py has no line at all')
        self.assertEqual(
            (lf, cr), (0, 0),
            'test_all.py mixes CRLF with LF/CR (%d CRLF, %d lone LF, %d lone CR)' % (crlf, lf, cr))

    def test_crlf_and_mixed_sources_match_cpython_on_both_builds(self):
        for name, data in PROGRAMS.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory(prefix='ail-pre92-') as directory:
                oracle = Path(directory) / (name + '_cpython.py')
                oracle.write_bytes(data)
                want = subprocess.run(
                    [sys.executable, '-B', str(oracle)], capture_output=True, timeout=120,
                    env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
                for general in (True, False):
                    exe, built = build(directory, name, data, general)
                    self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'),
                                     want.stdout.replace(b'\r\n', b'\n'),
                                     (name, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want.returncode,
                                     (name, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
