"""`ail explain FILE`: the typed-path status of every function, on eight probe programs.

The probe programs in lab/explain/progs/ carry their own ground truth in a `# expect:` line.
This module runs explain on the fast ones and compares every status with that line, so a change
that starts calling a general function typed (the one thing the command must never do) fails
here. It skips when no C compiler is installed: the statuses come from real builds.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / 'packaging'
PROGS = ROOT.parent / 'lab' / 'explain' / 'progs'

HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

FAST = ('t01_arith', 't02_str', 't04_list', 't05_dictlit', 't07_nested',
        'g01_dictbuild', 'g02_sorted', 'g05_nonret')

EXPECT = re.compile(r'^# expect:\s*(.*)$', re.M)
STATUS = re.compile(r'^\S+:\d+ (\S+)  (typed|general|unknown)\b', re.M)


def expected(text):
    found = EXPECT.search(text)
    if not found:
        raise AssertionError('probe has no # expect: line')
    return dict(part.split('=', 1) for part in found.group(1).split())


def run_explain(name, *flags):
    return subprocess.run(
        [sys.executable, '-m', 'ail_lang.explain', str(PROGS / (name + '.py'))] + list(flags),
        capture_output=True, text=True, cwd=str(PACKAGING))


def run_explain_path(path, *flags):
    return subprocess.run(
        [sys.executable, '-m', 'ail_lang.explain', str(path)] + list(flags),
        capture_output=True, text=True, cwd=str(PACKAGING))


@unittest.skipUnless(HAVE_CC, 'needs a C compiler: the statuses come from real builds')
class ExplainTest(unittest.TestCase):

    def test_status_column_matches_expectation(self):
        for name in FAST:
            with self.subTest(program=name):
                source = PROGS / (name + '.py')
                self.assertTrue(source.is_file(), 'missing probe %s' % source)
                done = run_explain(name)
                self.assertEqual(done.returncode, 0, done.stderr[-800:])
                got = dict(STATUS.findall(done.stdout))
                self.assertEqual(got, expected(source.read_text()),
                                 'explain output was:\n' + done.stdout)

    def test_json_parses_and_agrees(self):
        for name in FAST[:4]:
            with self.subTest(program=name):
                done = run_explain(name, '--json')
                self.assertEqual(done.returncode, 0, done.stderr[-800:])
                report = json.loads(done.stdout)
                self.assertEqual(report['schema'], 'ail.explain/1')
                self.assertIn(report['status'], ('typed', 'general', 'refused'))
                got = {entry['name']: entry['status'] for entry in report['functions']}
                self.assertEqual(got, expected((PROGS / (name + '.py')).read_text()))
                for entry in report['functions']:
                    self.assertIn('line', entry)
                    if entry['status'] == 'general':
                        self.assertTrue(entry.get('construct'), 'a general function needs a reason')

    def test_sibling_import_is_analyzed_from_the_real_file(self):
        with tempfile.TemporaryDirectory(prefix='ail-explain-import-') as workdir:
            root = Path(workdir)
            (root / 'helper.py').write_text(
                'def twice(x: int) -> int:\n    return x * 2\n', encoding='utf-8')
            main = root / 'main.py'
            main.write_text(
                'from helper import twice\n\n\n'
                'def run(n: int) -> int:\n    return twice(n) + 1\n\n\n'
                'def maybe(n: int) -> int:\n'
                '    if n > 0:\n        return n\n    return None\n\n\n'
                'def main() -> None:\n    print(run(maybe(3)))\n\n\nmain()\n', encoding='utf-8')
            done = run_explain_path(main)
            self.assertEqual(done.returncode, 0, done.stderr[-800:])
            self.assertEqual(dict(STATUS.findall(done.stdout)),
                             {'run': 'typed', 'maybe': 'general', 'main': 'typed'}, done.stdout)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ['helper.py', 'main.py'], 'the hiding copy was not removed')


if __name__ == '__main__':
    unittest.main()
