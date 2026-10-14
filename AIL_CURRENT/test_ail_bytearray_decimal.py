"""Direct decimal bytearray extension: independent formatting and effect order."""
import hashlib
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_c_objects as support
from test_ail_bytearray_receiver import oracle
from test_ail_map_fields import build

SOURCE = r'''
struct Box { data:bytearray; trace:str; calls:int; }
fn receiver(box:Box)->bytearray { box.trace+="R"; return box.data; }
fn argument(box:Box,action:int)->int {
 box.trace+="A"; box.calls+=1;
 if action==0 { box.data=bytearray(b"new"); }
 elif action==1 { box.data.clear(); }
 else { raise ValueError; }
 return -9223372036854775808;
}
fn run(n:int)->int {
 let output=bytearray();
 let values:list[int]=[0,1,-1,9,-9,10,-10,99,-99,100,-100,999,-999,
  1000,-1000,999999999999999999,-999999999999999999,
  1000000000000000000,-1000000000000000000,
  9223372036854775807,-9223372036854775808];
 for value in values { output.extend(str(value).encode(encoding="UTF_8",errors="strict")); output.append(44); }
 let power:int=1;
 for digit in range(19) {
  output.extend(str(power-1).encode()); output.append(44);
  output.extend(str(power).encode()); output.append(44);
  output.extend(str(-power).encode()); output.append(44);
  if digit<18 { power*=10; }
 }
 for i in range(n) {
  let value:int=i*1000003-123456789;
  output.extend(str(value).encode("utf8","strict")); output.append(44);
 }
 write_stdout_bytes(bytes(output));
 for action in range(3) {
  let box=Box(bytearray(b"old"),"",0); let held=box.data;
  try { receiver(box).extend(str(argument(box,action)).encode()); }
  except ValueError { write_stdout_bytes(b"caught"); }
  write_stdout_bytes(box.trace.encode()); write_stdout_bytes(str(box.calls).encode());
  write_stdout_bytes(bytes(held)); write_stdout_bytes(bytes(box.data));
 }
 write_stdout_bytes(b":continued"); return 0;
}
'''
SHADOW = r'''
fn str(value:int)->str { return "shadow"; }
fn run(n:int)->int { let output=bytearray(); output.extend(str(n).encode()); write_stdout_bytes(bytes(output)); return 0; }
'''
CALLABLE = r'''
fn format(value:int)->str { return "callable"; }
fn run(n:int)->int {
 let str:Callable[[int],str]=format; let output=bytearray();
 output.extend(str(n).encode()); write_stdout_bytes(bytes(output)); return 0;
}
'''
FLOAT = r'''
fn run(n:int)->int { let output=bytearray(); output.extend(str(1.5).encode()); write_stdout_bytes(bytes(output)); return 0; }
'''

class BytearrayDecimalTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def compare(self,executable,source,n):
        value,expected=oracle(source,n)
        result=subprocess.run([str(executable),str(n)],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,value,result.stderr[:2000].decode(errors='replace'))
        self.assertEqual(result.stderr,b'')
        if result.stdout!=expected:
            offset=next((i for i,(a,b) in enumerate(zip(result.stdout,expected)) if a!=b),
                        min(len(result.stdout),len(expected)))
            self.fail(f'first difference={offset}, sizes={len(result.stdout)}/{len(expected)}, '
                      f'sha256={hashlib.sha256(result.stdout).hexdigest()}/{hashlib.sha256(expected).hexdigest()}')

    def test_decimal_boundaries_many_values_receiver_effect_order_and_continuation(self):
        executable=build(self,'decimal',SOURCE+'fn main()->int { return run(int(sys.argv[1])); }')
        for n in (0,1,8193):
            with self.subTest(n=n): self.compare(executable,SOURCE,n)

    def supported_by_baseline_and_candidate(self,source):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            import pyfunc
            original=pyfunc._bytearray_method
            baseline=support.ROOT/'language_examples/bytearray_method_r616.baseline'
            namespace={}
            exec(compile(baseline.read_text(encoding='utf8'),str(baseline),'exec'),pyfunc.__dict__,namespace)
            messages=[]
            try:
                for method in (namespace['_bytearray_method'],original):
                    pyfunc._bytearray_method=method
                    try:
                        pyfunc.to_c(translate(source,module=True,imports=[]),name='run',strict=True)
                    except pyfunc.Unsupported as error:
                        messages.append(str(error))
                    else:
                        messages.append(None)
            finally:
                pyfunc._bytearray_method=original
            self.assertEqual(messages[1],messages[0],'candidate/baseline support or refusal differs')
            return messages[0] is None
        finally:
            sys.path.pop(0)

    def test_shadowed_function_and_float_fallback(self):
        for name,source in (('shadow',SHADOW),('float',FLOAT)):
            with self.subTest(name=name):
                if not self.supported_by_baseline_and_candidate(source): continue
                executable=build(self,name,source+'fn main()->int { return run(int(sys.argv[1])); }')
                self.compare(executable,source,17)

    def test_strict_codec_errors(self):
        expressions=('str(value).encode("ascii")','str(value).encode(errors="ignore")',
                     'str(value).encode("utf8","strict","extra")',
                     'str(value).encode("utf8",encoding="utf8")',
                     'str(value).encode(unknown="utf8")','str(value).encode(1)',
                     'str(value).encode(codec)')
        sources=[f'fn run(value:int)->int {{ let codec="utf8"; let output=bytearray(); output.extend({expression}); return 0; }}'
                 for expression in expressions]
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c,Unsupported
            for source in sources:
                with self.subTest(source=source):
                    with self.assertRaises(Unsupported):
                        to_c(translate(source,module=True,imports=[]),name='run',strict=True)
        finally:
            sys.path.pop(0)

    def test_callable_str_shadow_or_equal_existing_refusal(self):
        if not self.supported_by_baseline_and_candidate(CALLABLE): return
        executable=build(self,'callable',CALLABLE+'fn main()->int { return run(int(sys.argv[1])); }')
        self.compare(executable,CALLABLE,17)

if __name__=='__main__':
    unittest.main()
