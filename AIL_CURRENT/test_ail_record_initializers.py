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

SCALAR_BASELINE_SHA256={'import sys\n\ndef main() -> int:\n    xs: list[int] = [1, 2]\n    xs.reverse()\n    print(xs[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n': '8817d39ae35084b6469180bbf1a234d8c851dcbe3b10463ba94d8bb7ff6a1245', 'import sys\n\ndef main() -> int:\n    xs: list[float] = [1.5, 2.5]\n    xs.reverse()\n    print(xs[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n': 'b5344c52c8a0f2d4b6a19e54bf820883f5323bf5d0dd2be786ee294964c56347', 'import sys\n\nclass Box:\n\n    def __init__(self, ints: list[int], floats: list[float]):\n        self.ints = ints\n        self.floats = floats\n\ndef main() -> int:\n    b = Box([1], [1.5])\n    b.ints = [2]\n    b.floats = [2.5]\n    print(b.ints[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n': '353fcbe79dbba6495c26c061082725e1bda82c8a80162cbceca8eb5fe4297b96'}

WHOLE='import sys\n\nclass Source:\n\n    def __init__(self, count: int, ratio: float, data: bytes):\n        self.count = count\n        self.ratio = ratio\n        self.data = data\n\ndef choose(value: int=7) -> int:\n    return value\n\ndef inspect(rows: list[tuple[int, int]]) -> int:\n    return rows[0][0] + rows[0][1]\n\ndef main() -> int:\n    source = Source(9223372036854775807, 2.5, b\'\\x00x\')\n    ints: list[tuple[int, int]] = [(source.count, -1), (choose(), 5)]\n    print(len(ints))\n    print(ints[0][0])\n    print(inspect(ints))\n    ints = [(ints[-1][0], 8)]\n    copy: list[tuple[int, int]] = list(ints)\n    ints = []\n    print(copy[0][1])\n    floats: list[tuple[float, float]] = [(1.5, source.ratio), (0.0, -0.0)]\n    print(floats[0][1])\n    floats = []\n    floats.append((3.5, 4.5))\n    print(len(floats))\n    blobs: list[tuple[int, bytes]] = [(choose(), source.data)]\n    print(len(blobs[0][1]))\n    blobs = [(blobs[0][0], blobs[0][1] + b\'x\')]\n    print(len(blobs[0][1]))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

def generated(source):
 # (the C the legacy emitter writes: pinned and inspected here whatever AIL_IR says)
 saved=os.environ.get('AIL_IR');os.environ['AIL_IR']='0'
 try:return candidate.to_c(source,name='run',strict=True)
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
   'import sys\n\ndef main() -> int:\n    xs: list[int] = [(1, 2)]\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\ndef main() -> int:\n    xs: list[float] = [(1.5, 2.5)]\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\ndef main() -> int:\n    rows: list[tuple[int, int]] = [(1, 2, 3)]\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\ndef main() -> int:\n    rows: list[tuple[int, int]] = [(1, 2.5)]\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\ndef main() -> int:\n    rows: list[tuple[int, bytes]] = [(1, \'x\')]\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'struct Box {rows:list[tuple[int,int]];} fn main()->int {return 0;}',
  ]:
   with self.subTest(source=source),self.assertRaises((Unsupported,SyntaxErrorAIL)):generated(source)
 def test_existing_scalar_full_c_unchanged(self):
  for source in [
   'import sys\n\ndef main() -> int:\n    xs: list[int] = [1, 2]\n    xs.reverse()\n    print(xs[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\ndef main() -> int:\n    xs: list[float] = [1.5, 2.5]\n    xs.reverse()\n    print(xs[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
   'import sys\n\nclass Box:\n\n    def __init__(self, ints: list[int], floats: list[float]):\n        self.ints = ints\n        self.floats = floats\n\ndef main() -> int:\n    b = Box([1], [1.5])\n    b.ints = [2]\n    b.floats = [2.5]\n    print(b.ints[0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
  ]:
   self.assertEqual(hashlib.sha256(generated(source).encode('utf8')).hexdigest(),SCALAR_BASELINE_SHA256[source])

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class RecordInitializerNativeTests(unittest.TestCase):
 def test_whole_output_independent_python(self):
  expected=subprocess.run([sys.executable,'-X','utf8','-B','-c',oracle_source(WHOLE)],capture_output=True,timeout=30)
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