"""Every refusal message in lab/errux/progs scores at least its baseline, and no
compile leaks a Python traceback or raw C compiler text.

The corpus and scorer live in `lab/errux/`; this module imports `score.py` by path,
builds the 40 programs once, and checks:

1. `score.check()` — no program's message is below `baseline.json` (and no program
   that now builds is one CPython rejects);
2. no stderr contains `Traceback (most recent call last)` or a `program.c:` line with
   `error: ` from gcc/clang.

After a deliberate improvement, refresh the recorded scores with
`python3 lab/errux/score.py --write-baseline`.
"""
import importlib.util
import shutil
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORE_PATH = HERE.parent / 'lab' / 'errux' / 'score.py'
REFRESH = 'python3 lab/errux/score.py --write-baseline'


def load_scorer():
    spec = importlib.util.spec_from_file_location('ail_errux_score', SCORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_c_compiler():
    return any(shutil.which(name) for name in ('cc', 'gcc', 'clang'))


class ErruxRefusals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not has_c_compiler():
            raise unittest.SkipTest('no C compiler on PATH (cc/gcc/clang)')
        cls.scorer = load_scorer()
        cls.results = cls.scorer.evaluate_all()

    def test_every_message_meets_its_baseline(self):
        failures = self.scorer.check(self.results)
        self.assertEqual(failures, [],
                         'refusal messages regressed:\n  ' + '\n  '.join(failures)
                         + '\nIf the change is a deliberate improvement, refresh the baseline with:\n  '
                         + REFRESH)

    def test_no_traceback_or_c_compiler_error(self):
        leaked = []
        for item in self.results:
            stderr = item['stderr']
            if 'Traceback (most recent call last)' in stderr:
                leaked.append('%s: Python traceback' % item['program'])
            elif 'program.c:' in stderr and 'error: ' in stderr:
                leaked.append('%s: raw C compiler error' % item['program'])
        self.assertEqual(leaked, [],
                         'a compile leaked implementation text instead of a refusal:\n  '
                         + '\n  '.join(leaked)
                         + '\nIf the change is a deliberate improvement, refresh the baseline with:\n  '
                         + REFRESH)


if __name__ == '__main__':
    unittest.main()
