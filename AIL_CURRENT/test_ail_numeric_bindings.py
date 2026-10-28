"""Staged binding probes. Native execution is coordinated by the parent."""
import importlib.util, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE
sys.path[:0]=[str(ROOT),str(ROOT/'python/pkg-v12')]
import pyfunc as candidate
from ail_syntax import translate
from test_ail_scalar_list_mutations import MIXED_ITERATOR_WHOLE
from test_ail_callable_values import oracle_source
from test_ail_text_find_search import HEADERS
FLOW=r'''
fn exact(flag:int)->int {let floats:list[float]=[1.5];let ints:list[int]=[9223372036854775807];for item in floats {print(item);}for item in ints {if flag {return item-0;}continue;}return 0;}
fn main()->int {
 let ints:list[int]=[9223372036854775807,7];let floats:list[float]=[1.5,2.5];let empty:list[int]=[];
 for item in ints {print(item);break;}print(item);
 for item in floats {print(item);continue;}print(item);
 for item in empty {print(item);}print(item);for item in range(2) {print(item-1);}print(item);
 for item in ints {print(item);for item in ints {if item==7 {break;}}print(item);}
 try {for item in ints {print(item);raise ValueError;}}except ValueError {print(item);}
 item=9223372036854775807;print(item);item=1.5;print(item);item=7;print(item);let zero=0;try {item=9//zero;}except ZeroDivisionError {print(item);} print(exact(1));return 0;
}
'''
SHADOW_RANGE='''fn range()->list[float] {let values:list[float]=[1.5];return values;} fn probe()->float {for item in range() {return item;}return 0.0;} fn main()->int {print(probe());return 0;}'''
POST_ASSIGN='''fn main()->int {let floats:list[float]=[1.5];for item in floats {print(item);}item=7;item+=2;print(item);item*=3;print(item-0);return 0;}'''
AFTER_NESTED='''fn main()->int {let floats:list[float]=[1.5];let ints:list[int]=[9223372036854775807];for item in floats {print(item);}for item in ints {for item in ints {print(item-0);break;}print(item-0);}print(item-0);item=item-0;print(item);return 0;}'''
UNDER_NAME=MIXED_ITERATOR_WHOLE.replace('item','__item')
LITERAL_MARKER='''fn main()->int {let ints:list[int]=[7];let floats:list[float]=[1.5];for item in ints {print(item);}for item in floats {print(item);}print("__AIL_NB_wi_6974656d__");write_stdout_bytes(b"__AIL_NB_wi_6974656d__ = 0;\\n");return 0;}'''
MIN_MOD='''fn main()->int {let floats:list[float]=[1.5];for item in floats {print(item);}item=-9223372036854775808;print(item%-1);return 0;}'''
FATAL_EXPRESSIONS=('item+1','item*-1','-item','item//-1')
def fatal_source(expression):
 value='9223372036854775807' if expression=='item+1' else '-9223372036854775808'
 return 'fn main()->int {let floats:list[float]=[1.5];for item in floats {}item='+value+';print('+expression+');return 0;}'
CAST_BOUNDS=r'''
fn convert(bits:int)->int {let values:list[float]=float64_decode(integer_encode([bits],8,0),0);return int(values[0]);}
fn main()->int {
 print(convert(0));print(convert(4610560118520545280));print(convert(-9223372036854775808));
 print(convert(-4332462841530417152));print(convert(4890909195324358655));
 let bad:list[int]=[9221120237041090560,9218868437227405312,-4503599627370496,4890909195324358656,-4332462841530417151];
 for bits in bad {try {convert(bits);}except ValueError {print("ValueError");}except OverflowError {print("OverflowError");}}
 return 0;
}
'''
ORACLE_PRELUDE='''import builtins,math,struct,sys
def write_stdout_bytes(data):
 sys.stdout.flush();sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
_original_int=builtins.int
def int(value):
 if isinstance(value,float) and math.isnan(value):raise ValueError("cannot convert float NaN to integer")
 if isinstance(value,float) and (not math.isfinite(value) or not -2**63<=value<2**63):raise OverflowError("int64 conversion")
 return _original_int(value)
def integer_encode(values,width,order):return b"".join(_original_int(x).to_bytes(width,"little" if order==0 else "big",signed=True) for x in values)
def float64_decode(data,order):return [struct.unpack("<d" if order==0 else ">d",data[i:i+8])[0] for i in builtins.range(0,len(data),8)]
'''
BRANCH_JOIN='''fn probe(flag:int)->float {let item=0;if flag {item=1.5;}else {item=7;}return item+0;} fn compare(flag:int)->int {let item=0;if flag {item=1.5;}else {item=7;}if item==1 {return 1;}return 0;} fn main()->int {print(probe(1));print(int(probe(0)));print(compare(1));return 0;}'''
COMPARE_BOUNDARY='''fn main()->int {let floats:list[float]=[1.5];for item in floats {}item=9223372036854775807;let f=9223372036854775808.0;if item<f {print("less");}if item==f {print("bad");}if f>item {print("greater");}item=-9223372036854775808;if item== -9223372036854775808.0 {print("equal");}return 0;}'''
VECTORS=(BRANCH_JOIN,COMPARE_BOUNDARY,MIXED_ITERATOR_WHOLE,FLOW,SHADOW_RANGE,POST_ASSIGN,AFTER_NESTED,UNDER_NAME,LITERAL_MARKER,MIN_MOD,CAST_BOUNDS)
def generated(source):
 # (the C the legacy emitter writes: pinned and inspected here whatever AIL_IR says)
 saved=os.environ.get('AIL_IR');os.environ['AIL_IR']='0'
 try:return candidate.to_c(translate(source),name='run',strict=True)
 finally:
  if saved is None:os.environ.pop('AIL_IR',None)
  else:os.environ['AIL_IR']=saved
class NumericBindingTypeTests(unittest.TestCase):
 def test_original_mixed_iterator_integer_storage(self):
  c=generated(MIXED_ITERATOR_WHOLE)
  self.assertIn('v_item_nb.i',c);self.assertIn('v_item_nb.f',c);self.assertIn('v_item_nb.floating = 0',c);self.assertIn('v_item_nb.floating = 1',c)
  self.assertNotIn('__AIL_NB_',c)
 def test_nested_empty_break_continue_exception_and_return(self):
  c=generated(FLOW);self.assertNotIn('__AIL_NB_',c)
 def test_review_regressions_and_shadowed_signature(self):
  for source in VECTORS:
   with self.subTest(source=source):
    code=generated(source)
    if source!=LITERAL_MARKER:self.assertNotIn('__AIL_NB_',code)
  self.assertIn('double probe(void)',generated(SHADOW_RANGE))
  self.assertIn('v___item_nb.i',generated(UNDER_NAME))
 def test_strict_overflow_sources_use_existing_helpers(self):
  for expression in FATAL_EXPRESSIONS:
   code=generated(fatal_source(expression))
   self.assertIn('integer overflow',code)
  self.assertIn('pymod(',generated(MIN_MOD))
 def test_nonmixed_full_c_is_unchanged(self):
  import hashlib
  sources=('fn main()->int {let x=7;print(x);x+=2;print(x);return 0;}','fn main()->int {let x=1.5;print(x);return 0;}')
  pins=('20e0e98d62c708d2fb1982bc4b28e67fc83f136f165abe423d904971fc235978','9230c95deca3372ed0fce651a7fd6e1da7442e04ca7543dd88f17a570ac67e81')
  for source,pin in zip(sources,pins):self.assertEqual(hashlib.sha256(generated(source).encode()).hexdigest(),pin)
@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class NumericBindingNativeTests(unittest.TestCase):
 def test_independent_whole_output(self):
  for source in VECTORS:
   with self.subTest(source=source),tempfile.TemporaryDirectory(prefix='ail-numeric-r819-') as directory:
    expected=subprocess.run([sys.executable,'-X','utf8','-B','-c',ORACLE_PRELUDE+oracle_source(translate(source))],capture_output=True,timeout=30)
    self.assertEqual(expected.returncode,0,expected.stderr.decode(errors='replace'))
    path=Path(directory)/'probe.c';path.write_text(HEADERS+generated(source)+'\nint main(void){return (int)run();}\n',encoding='utf8')
    binary=Path(directory)/('probe.exe' if os.name=='nt' else 'probe')
    compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
    result=subprocess.run([compiler,'-std=c11','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
    self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
    actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
    self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),(0,expected.stdout.replace(b'\r\n',b'\n'),b''))
 def test_strict_integer_overflow_remains_fatal(self):
  for expression in FATAL_EXPRESSIONS:
   with self.subTest(expression=expression),tempfile.TemporaryDirectory(prefix='ail-numeric-overflow-') as directory:
    path=Path(directory)/'probe.c';path.write_text(HEADERS+generated(fatal_source(expression))+'\nint main(void){return (int)run();}\n',encoding='utf8')
    binary=Path(directory)/('probe.exe' if os.name=='nt' else 'probe')
    compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
    built=subprocess.run([compiler,'-std=c11','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
    self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
    result=subprocess.run([str(binary)],capture_output=True,timeout=30)
    self.assertEqual((result.returncode,result.stdout,result.stderr.replace(b'\r\n',b'\n')),(1,b'',b'integer overflow\n'))
if __name__=='__main__':unittest.main()