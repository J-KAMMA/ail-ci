"""Public strip overloads and exact declared codec value domains."""
import importlib.util, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'python/pkg-v12'))
import ail_builtin_api as api
import pyfunc
from ail_syntax import translate
from pyfront import Unsupported
from test_ail_callable_values import oracle_source
from test_ail_text_find_search import HEADERS
import test_ail_struct_lifetimes as resources

def entry(symbol):return api.query(symbol,source_root=ROOT)['entries'][0]

WHOLE=r'''
struct Box {text:str;}
fn receiver()->str {print("receiver");return "😀\0x😃";}
fn chars()->str {print("chars");return "😃";}
fn owner(box:Box)->Box {print("owner");return box;}
fn replace(box:Box)->str {print("replace");box.text="gone";return "😀\0";}
fn fail(box:Box)->str {print("fail");box.text="after-error";raise ValueError("chars failed");return "";}
fn half()->str {return jscharat("😀",0);}
fn text()->str {return "😀\0x😃";}
fn callback_trim(callback:Callable[[],str],characters:str)->str {return callback().rstrip(characters);}
fn main()->int {
 print(receiver().lstrip(chars()));print(receiver().rstrip(chars()));print(receiver().strip(chars()));
 print(callback_trim(text,"😃"));
 print("😀hello".lstrip("😃"));print("hello😀".rstrip("😃"));
 print("😀hello".lstrip(half()));print("hello😀".rstrip(half()));
 print("\0😀hello😀\0".strip("\0😀"));print("abc".lstrip(""));print("".rstrip("😀"));
 let left=Box("😀\0old😀\0");print(owner(left).text.lstrip(replace(left)));print(left.text);
 let right=Box("😀\0old😀\0");print(owner(right).text.rstrip(replace(right)));print(right.text);
 let both=Box("😀\0old😀\0");print(owner(both).text.strip(replace(both)));print(both.text);
 let failed=Box("before-error");
 try {let result=owner(failed).text.strip(fail(failed));print(result);}except ValueError {print("caught");}finally {print("finally");}
 print(failed.text);return 0;
}
'''
RESOURCE='''
class TextBox:
 def __init__(self,text:str):self.text=text

def replace_chars(box:TextBox)->int:
 box.text="gone"
 return 1

def step(i:int)->int:
 box=TextBox("😀\\0old😀\\0"+str(i%10))
 result=box.text.lstrip("😀\\0" if replace_chars(box) else "")
 total=len(result)
 box.text="😀\\0old😀\\0"
 result=box.text.rstrip("😀\\0" if replace_chars(box) else "")
 total+=len(result)
 try:
  fail_chars(box)
 except ValueError:
  total+=1
 finally:
  total+=len(box.text)
 return total

def fail_chars(box:TextBox)->int:
 chars="throw"+str(7)
 result=box.text.strip(chars)
 raise ValueError()
 return len(result)

def run(n:int)->int:
 total=0
 for i in range(n):total+=step(i)
 return total
'''
ORACLE_PRELUDE='''def jscharat(text,index):
 # UTF-16 unit index; the unit that starts an astral character yields the whole character and
 # the unit that ends one raises ValueError (a str never holds half a pair; 2026-10-11 decision).
 units=[]
 for character in text: units+=[character,None] if ord(character)>0xFFFF else [character]
 if not 0<=index<len(units): return ""
 if units[index] is None: raise ValueError
 return units[index]
'''

class BuiltinContractsTypeTests(unittest.TestCase):
 def test_strip_payload_has_both_overloads_and_ownership(self):
  for symbol in ('str.lstrip','str.rstrip'):
   value=entry(symbol)
   self.assertTrue(value['signature_known'])
   one=next(o for o in value['overloads'] if len(o['parameters'])==1)
   self.assertEqual(one['parameters'],[{'name':'chars','type':'str','ownership':'borrowed_view','access':'readonly'}])
   self.assertEqual(one['result'],{'type':'str','ownership':'owned_snapshot','access':'readonly'})
   self.assertFalse(one['receiver']['mutable'])
   self.assertIn([], [o['parameters'] for o in value['overloads']])
 def test_codec_constraints_match_runtime_domains(self):
  for symbol in ('integer_encode','integer_decode'):
   value=entry(symbol);rules=value['overloads'][0]['constraints']
   self.assertIn('width is 1, 2, 4 or 8; widths 1/2/4 are unsigned and width 8 is signed int64',rules)
   self.assertIn('byteorder 0 is little endian and 1 is big endian; bool follows integer 0/1',rules)
   self.assertIn('ValueError',value['known_errors'])
   self.assertTrue(any('even for empty input' in rule for rule in rules))
  self.assertIn('decode byte length must be divisible by width',entry('integer_decode')['overloads'][0]['constraints'])
  for symbol in ('float64_encode','float64_decode'):
   rules=entry(symbol)['overloads'][0]['constraints']
   self.assertTrue(any('even for empty input' in rule for rule in rules))
   self.assertIn('byteorder 0 is little endian and 1 is big endian; bool follows integer 0/1',rules)
  self.assertIn('decode byte length must be divisible by 8',entry('float64_decode')['overloads'][0]['constraints'])
 def test_supported_sources_and_refusal_boundaries(self):
  pyfunc.to_c(translate(WHOLE),name='run',strict=True)
  pyfunc.to_c(RESOURCE,name='run',strict=True,library=True)
  for method in ('strip','lstrip','rstrip'):
   for call in (method+'(b"x")',method+'("x","y")',method+'(chars="x")'):
    with self.subTest(call=call),self.assertRaises(Unsupported):
     pyfunc.to_c(translate('fn probe(text:str)->str {return text.'+call+';}',module=True),strict=True,library=True)
   with self.subTest(method=method),self.assertRaises(Unsupported):
    pyfunc.to_c(translate('fn probe(cb:Callable[[],str])->str {return cb.'+method+'("x");}',module=True),strict=True,library=True)

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class BuiltinContractsNativeTests(unittest.TestCase):
 check_lifetimes=resources.StructLifetimeTests.check_lifetimes
 def test_receiver_snapshots_exception_cleanup_zero_live(self):
  self.check_lifetimes(RESOURCE,sizes=(1,32,1024))
 def test_strip_whole_output_against_python_utf16_profile(self):
  expected=subprocess.run([sys.executable,'-X','utf8','-B','-c',ORACLE_PRELUDE+oracle_source(translate(WHOLE))],capture_output=True,timeout=30)
  self.assertEqual(expected.returncode,0,expected.stderr.decode(errors='replace'))
  with tempfile.TemporaryDirectory(prefix='ail-strip-contracts-') as directory:
   path=Path(directory)/'strip.c';path.write_text(HEADERS+pyfunc.to_c(translate(WHOLE),name='run',strict=True)+'\nint main(void){return (int)run();}\n',encoding='utf8')
   binary=Path(directory)/('strip.exe' if os.name=='nt' else 'strip')
   compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
   built=subprocess.run([compiler,'-std=c11','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
   self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
   actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
   self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),(0,expected.stdout.replace(b'\r\n',b'\n'),b''))
if __name__=='__main__':unittest.main()