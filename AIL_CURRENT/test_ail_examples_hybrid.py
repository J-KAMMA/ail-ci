"""The CPython-hybrid examples in `examples/hybrid/` match CPython and report what accelerated.

Every example is built with `ail build --cpython`, run with a small argument, and compared to
`python3` on stdout and exit status.  The README table is the source of truth for which examples
claim an accelerated function; for each `yes` the example's hot function must appear in
`build.json`, and for each `no` it must not.  The test also probes an int outside int64 through
`collatz.py`'s argv so the boundary falls back to the original Python function.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / 'examples' / 'hybrid'
README = EXAMPLES / 'README.md'
CLI = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

HOT = {
    'collatz': 'longest',
    'mandel_rows': 'mandel_checksum',
    'prime_count': 'prime_count',
    'checksum_text': 'rolling_hash',
    'sum_squares_list': 'sum_squares',
    'fallback_demo': 'triple',
}
ARGS = {
    'collatz': '200000',
    'mandel_rows': '80',
    'prime_count': '800',
    'checksum_text': '1000',
    'sum_squares_list': '50000',
    'fallback_demo': '11',
}


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=900)


def readme_rows():
    rows = {}
    for line in README.read_text(encoding='utf-8').splitlines():
        match = re.match(r'^\|\s*`([a-z0-9_]+)\.py`\s*\|\s*(yes|no)\s*\|', line)
        if match:
            rows[match.group(1)] = match.group(2) == 'yes'
    return rows


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class HybridExamples(unittest.TestCase):
    def build(self, tmp, name):
        src = EXAMPLES / (name + '.py')
        out = Path(tmp) / ('out-' + name)
        env = dict(os.environ, AIL_NO_CACHE='1')
        built = subprocess.run(
            [sys.executable, '-B', str(CLI), 'build', '--cpython', str(src), '-o', str(out)],
            cwd=str(tmp), env=env, capture_output=True, timeout=900)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
        return src, out / name, report

    def test_examples_match_cpython(self):
        rows = readme_rows()
        self.assertEqual(set(rows), set(HOT))
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-examples-') as tmp:
            for name in sorted(HOT):
                with self.subTest(example=name):
                    src, launcher, report = self.build(tmp, name)
                    if rows[name]:
                        self.assertIn(HOT[name], report['accelerated'], report)
                    else:
                        self.assertNotIn(HOT[name], report['accelerated'], report)
                    want = run([sys.executable, str(src), ARGS[name]], tmp)
                    got = run([str(launcher), ARGS[name]], tmp)
                    self.assertEqual(got.stdout, want.stdout)
                    self.assertEqual(got.returncode, want.returncode)

    def test_collatz_int_beyond_int64_falls_back(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-big-') as tmp:
            src, launcher, report = self.build(tmp, 'collatz')
            self.assertIn('longest', report['accelerated'], report)
            big = str(2 ** 63 + 1)
            want = run([sys.executable, str(src), big], tmp)
            got = run([str(launcher), big], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)


if __name__ == '__main__':
    unittest.main()
