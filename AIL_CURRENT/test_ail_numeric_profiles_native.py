"""Independent native numeric profile oracles and allocation cleanup."""
from collections import Counter
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from test_ail_numeric_profiles import compiler, ROOT
from ail_syntax import translate
from test_ail_exception_resources import ALLOCATOR

HEX_VALUES = [-(1 << 63), -(1 << 63) + 1, -65536, -16, -1, 0, 1, 15, 16, 255, (1 << 63) - 1]
HEX_SOURCE = 'fn main()->int {' + ''.join('print(hex(' + str(value) + '));' for value in HEX_VALUES) + 'return 0;}'
ONCE_SOURCE = '''struct State {calls:int;}
fn value(state:State)->int {state.calls+=1;return -9223372036854775808;}
fn main()->int {let state=State(0);let kept:str=hex(value(state));
print(kept);print(state.calls);return 0;}'''
SHADOW_SOURCE = 'fn hex(n:int)->int {return n+7;} fn main()->int {print(hex(5));return 0;}'
CALLABLE_SHADOW_SOURCE = 'fn target(n:int)->int {return n+1;} fn apply(hex:Callable[[int],int],n:int)->int {return hex(n);} fn main()->int {let hex:Callable[[int],int]=target;print(hex(4));print(apply(target,9));return 0;}'
CLEANUP_SOURCE = '''fn main()->int {let total:int=0;
for i in range(1024) {let text:str=hex(i);total+=len(text);
let xs:list[float]=[3.0,-0.0,0.0,float("inf"),float("-inf")];xs.sort();
let failed:list[float]=[1.0,float("nan"),-2.0];failed.sort();total+=len(failed);}
print(total);return 0;}'''


def sort_source(bits, catches=False):
    data = b''.join(value.to_bytes(8, 'little') for value in bits)
    operation = 'try {xs.sort();print("miss");}except ValueError {print("caught");}' if catches else 'xs.sort();'
    return ('fn main()->int {let seed:str=hex(0);let xs:list[float]=float64_decode(' + repr(data) + ',0);'
            + operation + 'print(float64_encode(xs,0).hex());return 0;}')


SORT_CASES = [[], [0x3ff0000000000000],
              [0x4008000000000000, 0xbff0000000000000, 0x3ff0000000000000],
              [0x7ff0000000000000, 0xfff0000000000000, 0x4000000000000000],
              [0x8000000000000000, 0, 0x8000000000000000, 0],
              [0x8000000000000000, 0x7ff0000000000000, 0, 0xfff0000000000000, 1, 0x8000000000000001]]
NAN_CASES = [[0x7ff8000000001234], [0x7ff8000000001234, 0x3ff0000000000000],
             [0x3ff0000000000000, 0x7ff8000000001234, 0x8000000000000000],
             [0x3ff0000000000000, 0x8000000000000000, 0xfff8000000005678]]
SOURCES = [HEX_SOURCE, ONCE_SOURCE, SHADOW_SOURCE, CALLABLE_SHADOW_SOURCE, CLEANUP_SOURCE,
           *(sort_source(bits) for bits in SORT_CASES), *(sort_source(bits, True) for bits in NAN_CASES)]


def generate(source):
    return compiler.to_c(translate(source), name='run', entry='main', strict=True)


class NativeGateSourceTests(unittest.TestCase):
    def test_all_native_gate_programs_generate_pure_c(self):
        for source in SOURCES:
            with self.subTest(source=source):
                self.assertTrue(generate(source))

    def test_borrowed_sort_is_refused_before_native(self):
        source = 'fn change(xs:list[float])->int {xs.sort();return len(xs);}'
        with self.assertRaises(compiler.Unsupported):
            compiler.to_c(translate(source, module=True), library=True, strict=True)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class NativeProfileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='ail-profiles-r821-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def execute(self, source):
        code = generate(source)
        cache_cleanup = ('for (int64_t i=0;i<ail__blk_cache_n;i++) count_free(ail__blk_cache[i].p);'
                         if 'ail__blk_cache_n' in code else '')
        cache_cleanup += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
        cache_cleanup += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in code else '')  # parked str-list vectors (cruntime ail__svec_cache)
        cache_cleanup += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in code else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host = '''
int main(void) {
    int result = (int)run();
    %s
    fprintf(stderr,"{\\"live\\":%%zu,\\"bytes\\":%%zu,\\"frames\\":%%d}\\n",
            live, live_bytes, ail_cleanup_top != NULL);
    return result;
}
''' % cache_cleanup
        path = self.root / 'main.c'
        path.write_text(ALLOCATOR + code + host, encoding='utf8')
        executable = self.root / ('main.exe' if os.name == 'nt' else 'main')
        cc = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        built = subprocess.run([cc, '-std=c11', '-O2', str(path), '-lm', '-o', str(executable)],
                               capture_output=True, timeout=120)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        result = subprocess.run([str(executable)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        metrics = json.loads(result.stderr)
        self.assertEqual((metrics['live'], metrics['bytes'], metrics['frames']), (0, 0, 0))
        return result.stdout.replace(b'\r\n', b'\n')

    def test_hex_complete_python_oracle(self):
        expected = ''.join(hex(value) + '\n' for value in HEX_VALUES).encode()
        self.assertEqual(self.execute(HEX_SOURCE), expected)

    def test_hex_once_evaluation_and_user_shadow(self):
        self.assertEqual(self.execute(ONCE_SOURCE), (hex(-(1 << 63)) + '\n1\n').encode())
        self.assertEqual(self.execute(SHADOW_SOURCE), b'12\n')
        self.assertEqual(self.execute(CALLABLE_SHADOW_SOURCE), b'5\n10\n')

    def test_float_sort_ascending_and_exact_bit_multiset(self):
        for bits in SORT_CASES:
            with self.subTest(bits=bits):
                output = self.execute(sort_source(bits))
                data = bytes.fromhex(output.decode().strip())
                self.assertEqual(len(data), 8 * len(bits))
                actual_bits = [int.from_bytes(data[i:i+8], 'little') for i in range(0, len(data), 8)]
                self.assertEqual(Counter(actual_bits), Counter(bits))
                actual = list(struct.unpack('<' + 'd' * len(bits), data))
                reference = sorted(struct.unpack('<' + 'd' * len(bits), b''.join(x.to_bytes(8, 'little') for x in bits)))
                self.assertEqual(actual, reference)
                self.assertTrue(all(a <= b for a, b in zip(actual, actual[1:])))

    def test_nan_sorted_like_cpython(self):
        for bits in NAN_CASES:
            with self.subTest(bits=bits):
                values = struct.unpack('<' + 'd' * len(bits),
                                       b''.join(x.to_bytes(8, 'little') for x in bits))
                ordered = b''.join(struct.pack('<d', value) for value in sorted(values))
                expected = b'miss\n' + ordered.hex().encode() + b'\n'
                self.assertEqual(self.execute(sort_source(bits, True)), expected)

    def test_repeated_success_and_runtime_cleanup(self):
        expected = sum(len(hex(i)) + 3 for i in range(1024))
        self.assertEqual(self.execute(CLEANUP_SOURCE), f'{expected}\n'.encode())


if __name__ == '__main__':
    unittest.main()
