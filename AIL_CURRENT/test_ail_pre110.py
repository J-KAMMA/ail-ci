"""pre110: the benchmark table keeps a ratio's printed side of 1.0.

The bench2 reviewer recorded a pre-existing display quirk: `numeric_scale_binary`'s
ail/base ratio printed `0.990 [0.981, 1.000] faster`, although its real upper bound
was 0.9996 and a range printed up to 1.000 reads as a tie.  `fmt` now adds digits
only when plain 3-decimal rounding would move a value across 1.0, so the printed
bounds agree with the unrounded verdict.  Ordinary ratios keep their 3 decimals.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from bench.compare import fmt  # noqa: E402


class Pre110Tests(unittest.TestCase):
    def test_upper_bound_below_one_keeps_faster(self):
        self.assertEqual(fmt({'median': 0.990, 'range': [0.981, 0.9996]}),
                         '0.990 [0.981, 0.9996] faster')

    def test_lower_bound_above_one_keeps_slower(self):
        self.assertEqual(fmt({'median': 1.001, 'range': [1.0004, 1.001]}),
                         '1.001 [1.0004, 1.001] slower')

    def test_true_tie_prints_both_sides(self):
        self.assertEqual(fmt({'median': 1.0, 'range': [0.9996, 1.0004]}),
                         '1.000 [0.9996, 1.0004] tie')

    def test_exact_one_is_a_tie(self):
        self.assertEqual(fmt({'median': 1.0, 'range': [1.0, 1.0]}),
                         '1.000 [1.000, 1.000] tie')

    def test_ordinary_ratios_stay_three_decimals(self):
        self.assertEqual(fmt({'median': 0.452, 'range': [0.451, 0.453]}),
                         '0.452 [0.451, 0.453] faster')
        self.assertEqual(fmt({'median': 1.414, 'range': [1.411, 1.420]}),
                         '1.414 [1.411, 1.420] slower')

    def test_median_without_a_range_uses_the_same_rule(self):
        self.assertEqual(fmt({'median': 0.9996, 'range': None}), '0.9996')
        self.assertEqual(fmt({'median': 1.0004, 'range': None}), '1.0004')

    def test_next_float_below_one_does_not_print_one(self):
        below = 0.9999999999999999
        self.assertEqual(fmt({'median': below, 'range': [below, below]}),
                         '0.9999999999999999 [0.9999999999999999, 0.9999999999999999] faster')


if __name__ == '__main__':
    unittest.main()
