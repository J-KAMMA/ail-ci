"""The typeshed conflict report: the tool's summary agrees with lab/typeshed/CONFLICTS.md.

No C compiler is needed: the tool imports the compiler's tables read-only, compares each with the
vendored signature table, and runs a CPython probe for every conflict.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
TOOL = REPO / 'tools' / 'typeshed_conflicts.py'
REPORT = REPO / 'lab' / 'typeshed' / 'CONFLICTS.md'


class TypeshedConflictsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.run([sys.executable, str(TOOL)], cwd=str(REPO),
                                  capture_output=True, text=True, timeout=300)
        cls.text = REPORT.read_text(encoding='utf-8')

    def test_summary_parses(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-2000:])
        match = re.search(r'^checked (\d+) agree (\d+) conflict (\d+) stub_obj (\d+)$',
                          self.proc.stdout, re.MULTILINE)
        self.assertIsNotNone(match, self.proc.stdout[-2000:])
        checked, agree, conflict, stub_obj = (int(x) for x in match.groups())
        self.assertEqual(checked, agree + conflict + stub_obj)

    def test_conflict_rows_match_and_each_has_a_verdict(self):
        match = re.search(r'^checked \d+ agree \d+ conflict (\d+) stub_obj \d+$',
                          self.proc.stdout, re.MULTILINE)
        self.assertIsNotNone(match)
        expected = int(match.group(1))
        section = self.text.split('## Conflicts', 1)[1].split('## ', 1)[0]
        rows = [line for line in section.splitlines()
                if line.startswith('| `') and not line.startswith('| _none_')]
        self.assertEqual(len(rows), expected)
        for row in rows:
            cells = [cell.strip() for cell in row.strip().strip('|').split('|')]
            self.assertEqual(len(cells), 6, row)
            self.assertTrue(cells[0].startswith('`') and cells[0].endswith('`'), row)
            self.assertIn(cells[5], ('rule', 'stub', 'neither'), row)

    def test_report_summary_matches_tool(self):
        match = re.search(r'`checked (\d+) agree (\d+) conflict (\d+) stub_obj (\d+)`', self.text)
        self.assertIsNotNone(match)
        self.assertIn('checked %s agree %s conflict %s stub_obj %s' % match.groups(),
                      self.proc.stdout)


if __name__ == '__main__':
    unittest.main()
