"""Raw integer-bit oracle, ownership, evaluation, widths and practical binary IO."""
import hashlib
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import unittest

import test_ail_c_objects as support
from test_ail_exception_resources import ALLOCATOR


def compiler():
    path = str(support.ROOT / 'python/pkg-v12')
    sys.path.insert(0, path)
    try:
        from pyfunc import to_c, Unsupported
    finally:
        sys.path.pop(0)
    def generate(*args, **kwargs):
        sys.path.insert(0, path)
        try:
            return to_c(*args, **kwargs)
        finally:
            sys.path.pop(0)
    return generate, Unsupported


class Float64CodecTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot

    def run_binary(self, exe, *args):
        return subprocess.run([str(exe), *map(str, args)], capture_output=True, timeout=120)

    def native(self, source):
        path = self.write('native.c', source)
        exe = self.root / ('native.exe' if os.name == 'nt' else 'native')
        cc = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        result = subprocess.run([cc, '-std=gnu11', '-O2', path, '-lm', '-o', exe],
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return exe

    def test_raw_bits_owned_results_and_relocated_source_free_module(self):
        obj = self.ail_build('codec', (support.ROOT / 'language_examples/binary_float64.ail').read_text(),
                             library=True)
        folder = self.root / '移動 😀'; folder.mkdir()
        moved = folder / obj.name
        obj.rename(moved); Path(str(obj) + '.json').rename(Path(str(moved) + '.json'))
        pins = self.snapshot(moved)
        exe = self.ail_build('roundtrip', '''fn main()->int {
let data=read_bytes(sys.argv[1]);let order=int(sys.argv[2]);
let saved=unpack_float64((b"x"+data+b"y")[1:-1],order);
let encoded=pack_float64(saved,1-order);
let later=unpack_float64(data[:8],order);let extra=pack_float64(later,order);
if len(saved)>0 {saved[0]=2.0;}
if pack_float64(unpack_float64(data,order),order)!=data {return 4;}
for i in range(19) {let temporary=float64_decode(data[:8],order);
let bytes_again=float64_encode(temporary,order);}
let seen=0;for value in float64_decode(data,order) {seen+=1;}
if seen!=len(saved) or len(float64_encode([],True))!=0 {return 5;}
write_stdout_bytes(encoded);return 0;
}''', moved)
        rng = random.Random(498)
        bits = [0, 1, 0x8000000000000000, 0x8000000000000001,
                0x0010000000000000, 0x000fffffffffffff, 0x7fefffffffffffff,
                0xffefffffffffffff, 0x7ff0000000000000, 0xfff0000000000000,
                0x7ff8000000000042, 0xfff8000000000042,
                0x7ff0000000000001, 0xfff0000000000001]
        bits += [1 << i for i in range(64)]
        bits += [rng.getrandbits(64) for _ in range(65537 - len(bits))]
        inp = self.root / '入力 😀.bin'
        for order in (0, 1):
            for count in (0, 1, 78, 8192, 8193, 65537):
                data = b''.join(x.to_bytes(8, 'little' if order == 0 else 'big') for x in bits[:count])
                inp.write_bytes(data)
                pin = (hashlib.sha256(data).hexdigest(), inp.stat().st_mtime_ns)
                actual = self.run_binary(exe, inp, order)
                expected = b''.join(data[i:i+8][::-1] for i in range(0, len(data), 8))
                self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (0, expected, b''))
                self.assertEqual((hashlib.sha256(inp.read_bytes()).hexdigest(), inp.stat().st_mtime_ns), pin)
        self.assertEqual(self.snapshot(moved), pins)

    def test_caught_invalid_input_evaluation_once_and_mutating_order(self):
        exe = self.ail_build('arguments', '''struct Source { data: bytes; values: list[float]; }
impl Source {
fn bytes_source(self)->bytes {print(1);return self.data;}
fn values_source(self)->list[float] {print(3);return self.values;}
fn order(self)->int {print(2);self.data=b"";let empty:list[float]=[];self.values=empty;return 0;}
fn fail(self)->int {print(4);raise ValueError;return 0;}
fn float64_decode(self,x:int,y:int)->int {return x+y;}
}
fn main()->int {
let s=Source(b"\\x00\\x00\\x00\\x00\\x00\\x00\\xf0\\x3f",[1.0,2.0]);
if s.float64_decode(7,8)!=15 {return 10;}
let decoded=float64_decode(s.bytes_source(),s.order());
if len(decoded)!=1 or decoded[0]!=1.0 {return 4;}
s.values=[1.0,2.0];let encoded=float64_encode(s.values_source(),s.order());
if len(encoded)!=16 {return 5;}
s.values=[1.0];let snapshot=float64_encode(s.values,s.order());
if len(snapshot)!=8 {return 6;}
s.data=b"\\x00\\x00\\x00\\x00\\x00\\x00\\xf0\\x3f";
let field_copy=float64_decode(s.data,s.order());
if len(field_copy)!=1 or field_copy[0]!=1.0 {return 9;}
try {float64_encode(s.values,s.fail());return 7;} except ValueError {let caught=1;}
let failures=0;let orders=[-9223372036854775808,-1,2,9223372036854775807];
for order in orders {
try {float64_decode(b"",order);} except ValueError {failures+=1;}
try {float64_encode([],order);} except ValueError {failures+=1;}
}
let lengths=[1,7,9];
for count in lengths {try {float64_decode(bytes(count),0);} except ValueError {failures+=1;}}
if failures!=11 {return 8;}
return 0;
}''')
        actual = self.run_binary(exe)
        self.assertEqual((actual.returncode, actual.stdout.replace(b'\r\n', b'\n'), actual.stderr),
                         (0, b'1\n2\n3\n2\n2\n2\n4\n', b''))

    def test_type_rejections_and_user_function_priority(self):
        to_c, Unsupported = compiler()
        expressions = ('float64_decode("x",0)', 'float64_decode(b"",0.0)',
                       'float64_decode(b"")', 'float64_decode(b"",order=0)',
                       'float64_encode([1],0)', 'float64_encode([1.0,2],0)',
                       'float64_encode((1.0,),0)', 'float64_encode([1.0],0.5)',
                       'float64_encode([1.0],0,0)', 'float64_encode([1.0],unknown)')
        for expression in expressions:
            with self.subTest(expression=expression), self.assertRaises(Unsupported):
                to_c('def run() -> int:\n value = ' + expression + '\n return len(value)\n',
                     name='run', strict=True)
        exe = self.ail_build('shadow', '''fn float64_decode(x:int,y:int)->int {return x+y;}
fn float64_encode(x:str,y:int)->int {return len(x)+y;}
fn main()->int {if float64_decode(7,8)!=15 or float64_encode("xy",9)!=11 {return 4;}return 0;}''')
        actual = self.run_binary(exe)
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (0, b'', b''))

    def test_allocation_failure_before_and_after_arena_registration(self):
        to_c, _ = compiler()
        code = to_c('def run(n: int) -> int:\n return len(float64_encode(float64_decode(bytes(8),0),0))\n',
                    name='run', strict=True)
        allocator = ALLOCATOR.replace('static size_t live, live_bytes, peak_bytes;',
                                     'static size_t live, live_bytes, peak_bytes;\nstatic int fail_after=-1;')
        allocator = allocator.replace('allocation_header *p = malloc',
                                      'if(fail_after>=0 && fail_after--==0)return NULL;\n allocation_header *p = malloc')
        allocator = allocator.replace('if (!ptr) return count_malloc(size);',
                                      'if (!ptr) return count_malloc(size);\n if(fail_after>=0 && fail_after--==0)return NULL;')
        host = r'''
static ail_barena failed_arena={0};
static void codec_exit(int status) {
 ail_barena_free(&failed_arena);
 if(live||live_bytes||ail_cleanup_top)exit(8);
 exit(status);
}
int main(int argc,char **argv) {
 if(argc!=2)return 2;int mode=atoi(argv[1]);double x=1;unsigned char data[8]={0};
 fail_after=mode==2?1:0;
 if(mode==0)ail_float64_decode((ail_bytes){data,8},0);
 else ail_float64_encode(&failed_arena,(ail_flist){&x,1,1},0);
 return 7;
}
'''
        exe = self.native(allocator + '\nstatic void codec_exit(int);\n#define _Exit codec_exit\n' + code + host)
        for mode in range(3):
            actual = self.run_binary(exe, mode)
            self.assertEqual((actual.returncode, actual.stdout), (1, b''), actual.stderr)
            self.assertIn(b'out of memory', actual.stderr)

    def test_native_span_guards_and_repeated_cleanup(self):
        to_c, _ = compiler()
        code = to_c('''def run(n: int) -> int:
 data = b"\\x00" * 8
 total = 0
 for i in range(n):
  values = float64_decode(data, 0)
  encoded = float64_encode(values, 1)
  try:
   float64_decode(data[:7], 0)
  except ValueError:
   total += len(encoded)
 return total
''', name='run', strict=True)
        drain = ('for(int64_t i=0;i<ail__blk_cache_n;i++) count_free(ail__blk_cache[i].p);'
                 'ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in code else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in code else '')  # parked str-list vectors (cruntime ail__svec_cache)
        host = r'''
int main(int argc,char **argv) {
 int m=argc==2?atoi(argv[1]):-1;ail_barena a={0};double x=1;
 if(m<0) {for(int n=1;n<=1001;n+=100) {
  if(run(n)!=8*n)return 4;DRAIN
  if(live||live_bytes||ail_cleanup_top||ail_exc_top!=-1)return 5;
 }return 0;}
 if(m==0)ail_float64_decode((ail_bytes){NULL,-1},0);
 if(m==1)ail_float64_decode((ail_bytes){NULL,8},0);
 if(m==2)ail_float64_encode(&a,(ail_flist){NULL,1,1},0);
 if(m==3)ail_float64_encode(&a,(ail_flist){&x,2,1},0);
 if(m==4)ail_float64_encode(&a,(ail_flist){&x,INT64_MAX/8+1,INT64_MAX/8+1},0);
 if(m==5)ail_float64_encode(NULL,(ail_flist){0},0);
 if(m==6){a.n=-1;ail_float64_encode(&a,(ail_flist){0},0);}
 if(m==7){a.cap=1;ail_float64_encode(&a,(ail_flist){0},0);}
 if(m==8){a.cap=INT64_MAX;a.n=INT64_MAX;a.blk=(unsigned char **)&x;
  ail_float64_encode(&a,(ail_flist){&x,1,1},0);}
 if(m==9)ail_float64_encode(&a,(ail_flist){&x,0,-1},0);
 if(m==10)ail_float64_decode((ail_bytes){NULL,0},2);
 if(m==11)ail_float64_encode(&a,(ail_flist){0},-1);
 return 6;
}
'''.replace('DRAIN', drain)
        exe = self.native(ALLOCATOR + code + host)
        actual = self.run_binary(exe)
        self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (0, b'', b''))
        for mode in range(12):
            actual = self.run_binary(exe, mode)
            self.assertEqual(actual.returncode, 1, (mode, actual.stderr))
            self.assertEqual(actual.stdout, b'')
            self.assertTrue(actual.stderr)

    def test_practical_binary_pipeline_large_input_and_errors(self):
        examples = support.ROOT / 'language_examples'
        exe = self.root / ('scale.exe' if os.name == 'nt' else 'scale')
        compiled = self.command('compile', examples / 'numeric_scale_binary_main.ail', '-o', exe)
        self.assertEqual(compiled.returncode, 0, compiled.stderr.decode(errors='replace'))
        src = self.root / 'numbers.bin'
        # Independent CPython arithmetic oracle; one multiply per finite input.
        values = [0.0, -0.0, 1.0, -3.0, 1e-300, 1e300, 2**-1022, 2**-1074]
        for order, prefix in ((0, '<'), (1, '>')):
            block = struct.pack(prefix + '8d', *values)
            expected_block = struct.pack(prefix + '8d', *(x * 0.5 for x in values))
            count = 1048576 if order == 0 else 1024
            data = block * count + struct.pack(prefix + 'd', 1.5)
            expected = expected_block * count + struct.pack(prefix + 'd', 0.75)
            src.write_bytes(data); pin = (hashlib.sha256(data).hexdigest(), src.stat().st_mtime_ns)
            actual = self.run_binary(exe, src, order, 0.5)
            self.assertEqual(actual.returncode, 0, actual.stderr)
            self.assertEqual(actual.stderr, b'')
            self.assertEqual(actual.stdout, expected)
            self.assertEqual((hashlib.sha256(src.read_bytes()).hexdigest(), src.stat().st_mtime_ns), pin)
        for order, prefix, text in ((0, '<', '\u3000-0000\u0085'),
                                    (1, '>', '\t+0001\u00a0'),
                                    (0, '<', '0'*129), (1, '>', '0'*129+'1')):
            data = struct.pack(prefix+'4d', 0.0, -0.0, 1.5, -3.0)
            expected = struct.pack(prefix+'4d', 0.0, -0.0, .75, -1.5)
            src.write_bytes(data); pin = (hashlib.sha256(data).hexdigest(), src.stat().st_mtime_ns)
            actual = self.run_binary(exe, src, text, .5)
            self.assertEqual((actual.returncode, actual.stdout, actual.stderr), (0, expected, b''))
            self.assertEqual((hashlib.sha256(src.read_bytes()).hexdigest(), src.stat().st_mtime_ns), pin)
        for text in ('9223372036854775807', '-9223372036854775808', '9223372036854775808',
                     '-9223372036854775809', '+'+'9'*129, '-'+'9'*129, '+', '-', '',
                     'not-an-int', '1_0', '１', '\x1c0', '0 1'):
            for filename in (src, self.root / 'missing'):
                actual = self.run_binary(exe, filename, text, .5)
                self.assertEqual((actual.returncode, actual.stdout), (2,b''))
                self.assertEqual(actual.stderr.splitlines(), [b'invalid binary64 records, order or finite factor'])
                self.assertEqual((hashlib.sha256(src.read_bytes()).hexdigest(), src.stat().st_mtime_ns), pin)
        for args, code in (([], 2), ([src, 2, 0.5], 2), ([src, 0, 'nan'], 2),
                           ([src, 0, 'inf'], 2), ([src, 0, 'invalid'], 2),
                           ([self.root / 'missing', 0, 0.5], 3)):
            actual = self.run_binary(exe, *args)
            self.assertEqual(actual.returncode, code, actual.stderr)
            self.assertEqual(actual.stdout, b'')
        src.write_bytes(b'123456789')
        actual = self.run_binary(exe, src, 0, 0.5)
        self.assertEqual(actual.returncode, 2)
        self.assertEqual(actual.stdout, b'')


if __name__ == '__main__':
    unittest.main()
