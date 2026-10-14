"""Review regressions with independent Python execution, staged compiler only."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from test_ail_numeric_bindings import generated,oracle_source,translate,HEADERS

CASES=[
 'fn probe(flag:int)->float {let item=0;if flag {item=1.5;}else {item=7;}return item+0;} fn main()->int {print(probe(1));return 0;}',
 'fn main()->int {let flag=1;let item=0;if flag {item=1.5;}else {item=7;}print(int(item==1));return 0;}',
 'fn range()->list[float] {return [1.5];} fn take() {for item in range() {return item;}return 0;} fn main()->int {print(take());return 0;}',
 'fn main()->int {let xs:list[float]=[1.5];for item in xs {} item=7;item+=2;print(item);return 0;}',
 'fn exact()->int {let floats:list[float]=[1.5];let ints:list[int]=[9223372036854775807];for item in floats {} for item in ints {return item-0;}return 0;} fn main()->int {print(exact());return 0;}',
 'fn main()->int {let floats:list[float]=[1.5];let ints:list[int]=[9223372036854775807];for __item in floats {} for __item in ints {print(__item);}return 0;}',
 'fn changed() {let xs:list[int]=[1];for item in xs {item=0.5;return item;}return 0.0;} fn main()->int {print(changed());return 0;}',
 'fn main()->int {let floats:list[float]=[1.5];let ints:list[int]=[];for item in floats {} for item in ints {} print(item);print("__AIL_NB_wi_6974656d__");return 0;}',
 'fn main()->int {let floats:list[float]=[float("nan")];let ints:list[int]=[];for item in floats {} for item in ints {} try {print(int(item));}except ValueError {print("invalid");}return 0;}',
]

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc'),'C compiler required')
class NumericBindingReviewNativeTests(unittest.TestCase):
 def test_review_regressions_against_python(self):
  compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
  for index,source in enumerate(CASES):
   with self.subTest(case=index),tempfile.TemporaryDirectory(prefix='ail-num-review-') as directory:
    reference=subprocess.run([os.sys.executable,'-X','utf8','-B','-c',oracle_source(translate(source))],capture_output=True,timeout=30)
    self.assertEqual(reference.returncode,0,reference.stderr.decode(errors='replace'))
    code=Path(directory)/'case.c';code.write_text(HEADERS+generated(source)+'\nint main(void){return (int)run();}\n',encoding='utf8')
    binary=Path(directory)/('case.exe' if os.name=='nt' else 'case')
    built=subprocess.run([compiler,'-std=c11','-O2',str(code),'-lm','-o',str(binary)],capture_output=True,timeout=180)
    self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
    actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
    self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),(reference.returncode,reference.stdout.replace(b'\r\n',b'\n'),reference.stderr))
 def test_signed64_float_conversion_profile(self):
  import math
  values=[-0.0,1.5,-1.5,-float(2**63),math.nextafter(float(2**63),-math.inf),float(2**63),math.nextafter(-float(2**63),-math.inf),math.nan,math.inf,-math.inf]
  expressions=[str(x) if math.isfinite(x) else 'float("'+str(x)+'")' for x in values]
  source='fn show(value:float)->void {try {print(int(value));}except ValueError {print("range");}return;} fn main()->int {'+''.join('show('+x+');' for x in expressions)+'return 0;}'
  expected=''.join((str(int(x)) if math.isfinite(x) and -2**63<=x<2**63 else 'range')+'\n' for x in values).encode()
  with tempfile.TemporaryDirectory(prefix='ail-float-int-review-') as directory:
   code=Path(directory)/'case.c';code.write_text(HEADERS+generated(source)+'\nint main(void){return (int)run();}\n',encoding='utf8')
   binary=Path(directory)/('case.exe' if os.name=='nt' else 'case')
   compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
   built=subprocess.run([compiler,'-std=c11','-O2',str(code),'-lm','-o',str(binary)],capture_output=True,timeout=180)
   self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
   actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
   self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),(0,expected,b''))
if __name__=='__main__':unittest.main()