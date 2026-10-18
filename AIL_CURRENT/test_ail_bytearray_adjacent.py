"""A bytearray.extend source that starts exactly where the bytearray's own block ends is a separate
allocation, not an alias. malloc implementations that pack small blocks (macOS) hand out such
neighbours, and the old `<=` bound killed the process with "invalid bytearray alias"; this places
the neighbour by hand so Linux sees the same layout."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
import cruntime  # noqa: E402

HOST = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <setjmp.h>
#include <math.h>
%s
int main(void) {
    static unsigned char block[64];          /* [0,16): the bytearray's block, [16,24): the neighbour */
    memcpy(block, "abc", 3); memcpy(block + 16, "XY", 2);
    ail_bytearray B = {1, 3, 16, block};
    ail_bytearray_extend(&B, (ail_bytes){block + 16, 2});
    printf("%%lld %%.5s\n", (long long)B.n, (const char *)block);
    ail_bytearray A = {1, 3, 16, block + 32};  /* a true alias into the unused tail still dies */
    memcpy(block + 32, "abc", 3);
    ail_bytearray_extend(&A, (ail_bytes){block + 32 + 8, 2});
    puts("not reached");
    return 0;
}
'''


@unittest.skipUnless(shutil.which('gcc') or shutil.which('cc'), 'no C compiler')
class AdjacentBlockTests(unittest.TestCase):
    def test_neighbouring_block_is_not_an_alias_but_a_tail_alias_still_is(self):
        compiler = os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        with tempfile.TemporaryDirectory() as tmp:
            source, exe = Path(tmp, 'adjacent.c'), Path(tmp, 'adjacent.exe')
            source.write_text(HOST % cruntime.emit(['BYTEARRAY']), encoding='utf8')
            built = subprocess.run([compiler, '-std=c11', '-O1', '-w', str(source), '-lm', '-o', str(exe)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout.splitlines()[:1], ['5 abcXY'], ran.stderr)
            self.assertNotEqual(ran.returncode, 0)
            self.assertIn('invalid bytearray alias', ran.stderr)
            self.assertNotIn('not reached', ran.stdout)


if __name__ == '__main__':
    unittest.main()
