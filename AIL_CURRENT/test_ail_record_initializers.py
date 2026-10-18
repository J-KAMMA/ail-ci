"""Record literals take the existing rows path, not scalar numeric snapshots."""
import hashlib, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'python/pkg-v12'))
import pyfunc as candidate
from ail_syntax import translate, SyntaxErrorAIL
from pyfront import Unsupported
from test_ail_callable_values import oracle_source
from test_ail_text_find_search import HEADERS

SCALAR_BASELINE_SHA256={'fn main()->int {let xs:list[int]=[1,2];xs.reverse();print(xs[0]);return 0;}': 'ea4fcf165d6b9cd70a84fbd80b12f6e0f28d7bf2a0bbe0b90de464f20564df0c', 'fn main()->int {let xs:list[float]=[1.5,2.5];xs.reverse();print(xs[0]);return 0;}': '9874ad18b845d30a0d9642169bbee9dc979552763954af53e9d65878933827a8', 'struct Box {ints:list[int];floats:list[float];} fn main()->int {let b=Box([1],[1.5]);b.ints=[2];b.floats=[2.5];print(b.ints[0]);return 0;}': '776799ea4d60bf322ac81789196a44da09f68d4b569b17f3489545ae81b40d95'}

WHOLE=r'''
struct Source {count:int;ratio:float;data:bytes;}
fn choose(value:int=7)->int {return value;}
fn inspect(rows:list[tuple[int,int]])->int {return rows[0][0]+rows[0][1];}
fn main()->int {
 let source=Source(9223372036854775807,2.5,b"\0x");
 let ints:list[tuple[int,int]]=[(source.count,-1),(choose(),5)];
 print(len(ints));print(ints[0][0]);print(inspect(ints));
 ints=[(ints[-1][0],8)];let copy:list[tuple[int,int]]=list(ints);ints=[];print(copy[0][1]);
 let floats:list[tuple[float,float]]=[(1.5,source.ratio),(0.0,-0.0)];print(floats[0][1]);
 floats=[];floats.append((3.5,4.5));print(len(floats));
 let blobs:list[tuple[int,bytes]]=[(choose(),source.data)];print(len(blobs[0][1]));
 blobs=[(blobs[0][0],blobs[0][1]+b"x")];print(len(blobs[0][1]));return 0;
}
'''

def generated(source):
 # (the C the legacy emitter writes: pinned and inspected here whatever AIL_IR says)
 saved=os.environ.get('AIL_IR');os.environ['AIL_IR']='0'
 try:return candidate.to_c(translate(source),name='run',strict=True)
 finally:
  if saved is None:os.environ.pop('AIL_IR',None)
  else:os.environ['AIL_IR']=saved

class RecordInitializerTypeTests(unittest.TestCase):
 def test_three_record_kinds_empty_and_nonempty(self):
  for kind,values in [('int,int','(1,2)'),('float,float','(1.5,2.5)'),('int,bytes','(7,b"x")')]:
   for initializer in ('[]','['+values+']'):
    with self.subTest(kind=kind,initializer=initializer):
     generated('fn main()->int {let rows:list[tuple['+kind+']]='+initializer+';print(len(rows));return 0;}')
 def test_legacy_frontend_uses_same_record_classification(self):
  for kind,values in [('int,int','(1,2)'),('float,float','(1.5,2.5)'),('int,bytes','(7,b"x")')]:
   source='def run():\n rows:list[tuple['+kind+']]=['+values+']\n return len(rows)\n'
   with self.subTest(kind=kind):candidate.to_c(source,name='run',strict=True,library=True)
 def test_defaults_fields_local_copy_access_and_replacement(self):generated(WHOLE)
 def test_scalar_tuple_conflicts_and_unimplemented_record_fields_refused(self):
  for source in [
   'fn main()->int {let xs:list[int]=[(1,2)];return 0;}',
   'fn main()->int {let xs:list[float]=[(1.5,2.5)];return 0;}',
   'fn main()->int {let rows:list[tuple[int,int]]=[(1,2,3)];return 0;}',
   'fn main()->int {let rows:list[tuple[int,int]]=[(1,2.5)];return 0;}',
   'fn main()->int {let rows:list[tuple[int,bytes]]=[(1,"x")];return 0;}',
   'struct Box {rows:list[tuple[int,int]];} fn main()->int {return 0;}',
  ]:
   with self.subTest(source=source),self.assertRaises((Unsupported,SyntaxErrorAIL)):generated(source)
 def test_existing_scalar_full_c_unchanged(self):
  for source in [
   'fn main()->int {let xs:list[int]=[1,2];xs.reverse();print(xs[0]);return 0;}',
   'fn main()->int {let xs:list[float]=[1.5,2.5];xs.reverse();print(xs[0]);return 0;}',
   'struct Box {ints:list[int];floats:list[float];} fn main()->int {let b=Box([1],[1.5]);b.ints=[2];b.floats=[2.5];print(b.ints[0]);return 0;}',
  ]:
   self.assertEqual(hashlib.sha256(generated(source).encode('utf8')).hexdigest(),SCALAR_BASELINE_SHA256[source])

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class RecordInitializerNativeTests(unittest.TestCase):
 def test_whole_output_independent_python(self):
  expected=subprocess.run([sys.executable,'-X','utf8','-B','-c',oracle_source(translate(WHOLE))],capture_output=True,timeout=30)
  self.assertEqual(expected.returncode,0,expected.stderr.decode(errors='replace'))
  with tempfile.TemporaryDirectory(prefix='ail-record-r821-') as directory:
   path=Path(directory)/'records.c';path.write_text(HEADERS+generated(WHOLE)+'\nint main(void){return (int)run();}\n',encoding='utf8')
   binary=Path(directory)/('records.exe' if os.name=='nt' else 'records')
   compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
   result=subprocess.run([compiler,'-std=c11','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
   self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
   result=subprocess.run([str(binary)],capture_output=True,timeout=30)
   self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,expected.stdout.replace(b'\r\n',b'\n'),b''))
if __name__=='__main__':unittest.main()