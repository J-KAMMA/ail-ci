"""Integer codec: independent whole-buffer oracle, boundaries and ownership."""
import hashlib
import random
import struct
import subprocess
import unittest
from pathlib import Path

import test_ail_c_objects as support
import test_ail_float64_codec as float_support
from test_ail_exception_resources import ALLOCATOR

compiler = float_support.compiler


class IntegerCodecTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    snapshot = support.CObjectTests.snapshot
    native = float_support.Float64CodecTests.native

    def run_binary(self, executable, *args):
        return subprocess.run([str(executable), *map(str, args)],
                              capture_output=True, timeout=120)

    def assert_binary(self, actual, expected):
        self.assertEqual((actual.returncode, actual.stderr), (0, b''))
        self.assertEqual(actual.stdout, expected)

    def test_all_widths_orders_domains_large_buffer_and_owned_results(self):
        exe = self.ail_build('roundtrip', r'''fn main()->int {
let data=read_bytes(sys.argv[1]);let width=int(sys.argv[2]);let order=int(sys.argv[3]);
let values=integer_decode((b"x"+data+b"y")[1:-1],width,order);
let saved=integer_encode(values,width,1-order);
let same=integer_encode(values,width,order);
if len(values)>0 {let original=values[0];values[0]=0;
let fresh=integer_decode(data,width,order);if fresh[0]!=original {return 4;}}
for i in range(23) {let temporary=integer_decode(data[:width],width,order);
let encoded=integer_encode(temporary,width,order);}
if same!=data or data!=read_bytes(sys.argv[1]) {return 5;}
let empty:list[int]=[];if len(integer_encode(empty,width,order))!=0 {return 6;}
if len(integer_decode(b"",width,order))!=0 {return 7;}
write_stdout_bytes(saved);write_stdout_bytes(same);return 0;
}''')
        rng = random.Random(564)
        path = self.root / '入力 😀.bin'
        for width, code in ((1, 'B'), (2, 'H'), (4, 'I'), (8, 'q')):
            low, high = (-(1 << 63), (1 << 63)-1) if width == 8 else (0, (1 << (8*width))-1)
            values = list(range(high+1)) if width <= 2 else [low, low+1, -1, 0, 1, high-1, high] if width == 8 else [0, 1, high-1, high]
            count = (400012 + width-1)//width
            values += [rng.randint(low, high) for _ in range(max(0, count-len(values)))]
            for order, prefix in ((0, '<'), (1, '>')):
                for chosen in ([], values[:1], values):
                    data = struct.pack(prefix + str(len(chosen)) + code, *chosen)
                    expected = b''.join(value.to_bytes(width, 'big' if order == 0 else 'little',
                                                      signed=width == 8) for value in chosen)
                    path.write_bytes(data)
                    pin = (hashlib.sha256(data).digest(), path.stat().st_mtime_ns)
                    with self.subTest(width=width, order=order, count=len(chosen)):
                        self.assert_binary(self.run_binary(exe, path, width, order), expected + data)
                        self.assertEqual((hashlib.sha256(path.read_bytes()).digest(), path.stat().st_mtime_ns), pin)

    def test_validation_snapshot_and_argument_evaluation(self):
        exe = self.ail_build('arguments', r'''struct Source {data:bytes;values:list[int];}
impl Source {
fn input(self)->bytes {print(1);return self.data;}
fn items(self)->list[int] {print(1);return self.values;}
fn width(self)->int {print(2);self.data=b"";self.values=[9];return 2;}
fn order(self)->int {print(3);self.data=b"";self.values=[8];return 0;}
fn fail(self)->int {print(4);raise ValueError;return 0;}
fn integer_decode(self,x:int,y:int,z:int)->int {return x+y+z;}
}
fn main()->int {
let s=Source(b"\x01\x00\xff\xff",[1,65535]);
if s.integer_decode(1,2,3)!=6 {return 10;}
let a=integer_decode(s.input(),s.width(),s.order());if len(a)!=2 or a[1]!=65535 {return 4;}
s.values=[1,65535];let b=integer_encode(s.items(),s.width(),s.order());
if b!=b"\x01\x00\xff\xff" {return 5;}
s.data=b"\x01\x00";let c=integer_decode(s.data,s.width(),s.order());
if len(c)!=1 or c[0]!=1 {return 6;}
s.values=[7];let d=integer_encode(s.values,s.width(),s.order());if d!=b"\x07\x00" {return 7;}
try {integer_encode(s.values,2,s.fail());return 8;} except ValueError {let caught=1;}
let failures=0;let invalid=[-9223372036854775808,-1,0,3,5,7,9,9223372036854775807];
for width in invalid {
try {integer_encode([],width,0);} except ValueError {failures+=1;}
try {integer_decode(b"",width,0);} except ValueError {failures+=1;}}
let orders=[-9223372036854775808,-1,2,9223372036854775807];
let widths=[1,2,4,8];for width in widths {for order in orders {
try {integer_encode([],width,order);} except ValueError {failures+=1;}
try {integer_decode(b"",width,order);} except ValueError {failures+=1;}}
for count in range(1,width) {try {integer_decode(bytes(count),width,0);}
except ValueError {failures+=1;}}
if width!=8 {try {integer_encode([-1],width,0);} except ValueError {failures+=1;}}}
let limits=[256,65536,4294967296];let small=[1,2,4];
for i in range(3) {try {integer_encode([limits[i]],small[i],1);} except ValueError {failures+=1;}}
if failures!=65 {return 9;}return 0;
}''')
        actual = self.run_binary(exe)
        self.assertEqual((actual.returncode, actual.stdout.replace(b'\r\n', b'\n'), actual.stderr),
                         (0, b'1\n2\n3\n1\n2\n3\n2\n3\n2\n3\n4\n', b''))

    def test_type_arity_rejection_shadowing_and_source_free_module(self):
        to_c, Unsupported = compiler()
        expressions = ('integer_decode("x",1,0)', 'integer_decode(b"",1.0,0)',
                       'integer_decode(b"",1,0.0)', 'integer_decode(b"",1)',
                       'integer_decode(b"",1,0,0)', 'integer_decode(b"",width=1,order=0)',
                       'integer_encode([1.0],1,0)', 'integer_encode([1,2.0],1,0)',
                       'integer_encode((1,),1,0)', 'integer_encode([1],1.0,0)',
                       'integer_encode([1],1,0.5)', 'integer_encode([1],1)',
                       'integer_encode([1],1,0,0)')
        for expression in expressions:
            with self.subTest(expression=expression), self.assertRaises(Unsupported):
                to_c('def run() -> int:\n value = ' + expression + '\n return len(value)\n',
                     name='run', strict=True)
        shadow = self.ail_build('shadow', '''fn integer_decode(x:int,y:int,z:int)->int {return x+y+z;}
fn integer_encode(x:str,y:int,z:int)->int {return len(x)+y+z;}
fn main()->int {if integer_decode(1,2,3)!=6 or integer_encode("xy",3,4)!=9 {return 4;}return 0;}''')
        self.assert_binary(self.run_binary(shadow), b'')
        obj = self.ail_build('codec', '''use binary_integers;
fn reverse(data:bytes)->bytes {
return pack_integers(unpack_integers(data,8,0),8,1);}''', library=True)
        folder = self.root / '移動 😀'; folder.mkdir()
        moved = folder / obj.name
        obj.rename(moved); Path(str(obj)+'.json').rename(Path(str(moved)+'.json'))
        pin = self.snapshot(moved)
        exe = self.ail_build('module', '''fn main()->int {
write_stdout_bytes(reverse(read_bytes(sys.argv[1])));return 0;}''', moved)
        values = [-(1 << 63), -1, 0, (1 << 63)-1] * 12501
        path = self.root / 'module.bin'; path.write_bytes(struct.pack('<'+str(len(values))+'q', *values))
        self.assert_binary(self.run_binary(exe, path), struct.pack('>'+str(len(values))+'q', *values))
        self.assertEqual(self.snapshot(moved), pin)

    def test_native_span_guards_and_repeated_cleanup(self):
        to_c, _ = compiler()
        code = to_c('''def run(n: int) -> int:
 data = b"\\xff\\xff"
 total = 0
 for i in range(n):
  values = integer_decode(data, 2, 0)
  encoded = integer_encode(values, 2, 1)
  try:
   integer_decode(data[:1], 2, 0)
  except ValueError:
   total += len(encoded)
 return total
''', name='run', strict=True)
        drain = ('for(int64_t i=0;i<ail__blk_cache_n;i++) count_free(ail__blk_cache[i].p);'
                 'ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in code else '')
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in code else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in code else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host = r'''
int main(int argc,char **argv) {
 int m=argc==2?atoi(argv[1]):-1;ail_barena a={0};int64_t x=1;
 if(m<0) {for(int n=1;n<=1001;n+=100) {
  if(run(n)!=2*n)return 4;DRAIN
  if(live||live_bytes||ail_cleanup_top||ail_exc_top!=-1)return 5;
 }return 0;}
 if(m==0)ail_integer_decode((ail_bytes){NULL,-1},1,0);
 if(m==1)ail_integer_decode((ail_bytes){NULL,8},8,0);
 if(m==2)ail_integer_encode(&a,(ail_list){NULL,1,1},1,0);
 if(m==3)ail_integer_encode(&a,(ail_list){&x,2,1},1,0);
 if(m==4)ail_integer_encode(&a,(ail_list){&x,INT64_MAX/8+1,INT64_MAX/8+1},8,0);
 if(m==5)ail_integer_encode(NULL,(ail_list){0},1,0);
 if(m==6){a.n=-1;ail_integer_encode(&a,(ail_list){0},1,0);}
 if(m==7){a.cap=1;ail_integer_encode(&a,(ail_list){0},1,0);}
 if(m==8){a.cap=INT64_MAX;a.n=INT64_MAX;a.blk=(unsigned char **)&x;
  ail_integer_encode(&a,(ail_list){&x,1,1},1,0);}
 if(m==9)ail_integer_encode(&a,(ail_list){&x,0,-1},1,0);
 if(m==10)ail_integer_decode((ail_bytes){NULL,0},1,2);
 if(m==11)ail_integer_encode(&a,(ail_list){0},0,0);
 if(m==12)ail_integer_decode((ail_bytes){(const unsigned char *)&x,INT64_MAX},1,0);
 return 6;
}
'''.replace('DRAIN', drain)
        exe = self.native(ALLOCATOR + code + host)
        self.assert_binary(self.run_binary(exe), b'')
        for mode in range(13):
            actual = self.run_binary(exe, mode)
            self.assertEqual(actual.returncode, 1, (mode, actual.stderr))


if __name__ == '__main__':
    unittest.main()
