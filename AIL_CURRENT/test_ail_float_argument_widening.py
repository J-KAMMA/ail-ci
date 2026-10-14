"""Integer-to-float call conversion preserves the declared ABI at int64 boundaries."""
import os
import shutil
import unittest

import test_ail_c_objects as support


PROVIDER = '''fn take(value:float)->float {return value;}
fn nested(value:float)->float {return take(value);}
'''
VALUES = [-(1 << 63), -(1 << 53) - 1, -(1 << 53), -1, 0, 1,
          (1 << 53) - 1, 1 << 53, (1 << 53) + 1, (1 << 53) + 3, (1 << 63) - 1]


def entry():
    checks = ''.join(f'if {function}({value})!={float(value)!r} {{return 1;}}'
                     for function in ('take', 'nested') for value in VALUES)
    return 'fn main()->int {' + checks + 'if take(1.5)!=1.5 {return 2;} print(1);return 0;}'


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class FloatArgumentWideningTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def test_direct_and_source_free_calls_match_independent_float_conversion(self):
        direct = self.ail_build('direct_widening', PROVIDER + entry())
        self.check_run(direct, '1\n')
        provider = self.ail_build('widening_provider', PROVIDER, library=True)
        before = support.CObjectTests.snapshot(self, provider)
        linked = self.ail_build('linked_widening', entry(), provider)
        self.check_run(linked, '1\n')
        self.assertEqual(support.CObjectTests.snapshot(self, provider), before)


if __name__ == '__main__':
    unittest.main()
