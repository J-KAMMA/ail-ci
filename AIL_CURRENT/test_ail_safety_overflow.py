"""The overflow suite's safe cells stay safe: int64 stops loudly, and the exact build still matches.

`lab/safety/overflow/` holds 24 programs and the five-mode table `RESULTS.md` (job safeovf1). This
module reads that table, takes every program whose `default` and `exact` cells are `match` or
`ovf-stop`, rebuilds it in both modes, runs it under the same limits the table used
(`ulimit -v 1500000`, `timeout 20`) and re-classifies it against CPython 3.12:

  * the `default` build must still be `match` or `ovf-stop` -- a value that fits prints CPython's
    value, and a value beyond int64 prints the correct prefix and then stops with an
    `OverflowError: integer overflow` last stderr line, never a wrapped or different number;
  * the `exact` build must still be `match` or `ovf-stop` (the table records five exact cells that
    are still loud int64 stops: `int()` from text and augmented assignment on a list item, a class
    field and a dict value); a cell the table recorded as `match` must stay `match`.

The module skips when there is no C compiler, since every mode builds C.
"""
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / 'lab' / 'safety' / 'overflow'
RUNNER = LAB / 'run.py'
RESULTS = LAB / 'RESULTS.md'
MODES = ('typed', 'default', 'general', 'hybrid', 'exact')
SAFE = ('match', 'ovf-stop')
HAVE_CC = os.name == 'posix' and (shutil.which('gcc') or shutil.which('cc')) is not None


def load_runner():
    spec = importlib.util.spec_from_file_location('overflow_run', str(RUNNER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def table_rows(text):
    """{program: {mode: class}} from the RESULTS.md table."""
    rows = {}
    for line in text.splitlines():
        match = re.match(r'^\|\s*`([^`]+\.py)`\s*\|(.+)\|\s*$', line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(2).split('|')]
        if len(cells) != len(MODES):
            continue
        rows[match.group(1)] = dict(zip(MODES, cells))
    return rows


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
@unittest.skipUnless(RUNNER.is_file() and RESULTS.is_file(), 'needs lab/safety/overflow/run.py and RESULTS.md')
class OverflowRatchet(unittest.TestCase):
    """The table's default and exact results do not regress."""

    @classmethod
    def setUpClass(cls):
        cls.ovf = load_runner()
        cls.rows = table_rows(RESULTS.read_text(encoding='utf-8'))
        cls.selected = {program: row for program, row in cls.rows.items()
                        if row['default'] in SAFE and row['exact'] in SAFE}

    def test_the_table_has_24_programs_and_120_cells(self):
        self.assertEqual(len(self.selected), len(self.rows))
        self.assertEqual(len(self.rows), 24, sorted(set(self.rows) ^ set(
            p.name for p in LAB.glob('*.py') if p.name != 'run.py')))
        self.assertEqual(len(self.rows) * len(MODES), 120)
        for program, row in self.rows.items():
            for mode in MODES:
                self.assertIn(row[mode], ('match', 'ovf-stop', 'refused', 'stop-differs',
                                          'silent-wrong', 'crash', 'n/a'), (program, mode))

    def test_safe_cells_stay_safe(self):
        self.assertGreater(len(self.selected), 0, 'no program is safe in both default and exact')
        for program, recorded in sorted(self.selected.items()):
            with self.subTest(program=program):
                source = LAB / program
                cp_rc, cp_out, cp_err, cp_timeout = self.ovf.run_once(
                    [sys.executable, '-B', str(source)], str(LAB))
                self.assertFalse(cp_timeout, program)
                oracle = (cp_rc, cp_out, cp_err)
                for mode in ('default', 'exact'):
                    with tempfile.TemporaryDirectory(prefix='ail-ovf-ratchet-') as workdir:
                        out = Path(workdir) / 'out.bin'
                        built, message = self.ovf.build(source, out, mode, workdir)
                        self.assertTrue(built, '%s %s did not build: %s' % (program, mode, message[-2000:]))
                        rc, stdout, stderr, timed_out = self.ovf.run_once([str(out)], workdir)
                        self.assertFalse(timed_out, (program, mode))
                        got, note = self.ovf.classify(oracle, (rc, stdout, stderr), timed_out)
                        self.assertIn(got, SAFE, '%s %s became %s: %s (stdout %r, stderr %r)'
                                      % (program, mode, got, note, stdout, stderr[-500:]))
                        if recorded[mode] == 'match':
                            self.assertEqual(got, 'match', '%s %s was match, now %s: %s'
                                             % (program, mode, got, note))


if __name__ == '__main__':
    unittest.main()
