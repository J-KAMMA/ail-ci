"""Bare raise follows CPython's active handler across scopes and object units."""
import ast
import json
import os
import shutil
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_callable_values as callbacks
import test_ail_c_objects as support
import test_ail_finally as finally_support
from test_ail_exception_resources import ALLOCATOR, ROOT


PROVIDER = '''def rethrow() -> int:
 raise
 return 0
def v__handled_entry() -> int:
 return 17
def v__handled_boundary() -> int:
 return 19
def _ail_handled1() -> int:
 return 23
def _ail_finally_cleanup1_handled() -> int:
 return 29
def ail_reraise() -> int:
 return 41
def function_name_probe() -> int:
 try:
  raise ValueError()
 except ValueError:
  print(v__handled_entry()); print(v__handled_boundary()); print(_ail_handled1())
 return 0
def local_name_probe() -> int:
 _handled_entry: int = 31
 _handled_boundary: int = 37
 try:
  raise ValueError()
 except ValueError:
  print(_handled_entry); print(_handled_boundary)
 return 0
def nested_handler() -> int:
 try:
  raise ValueError()
 except ValueError:
  try:
   rethrow()
  except ValueError:
   print("nested ValueError")
 return 17
def invoke(cb: Callable[[], int]) -> int:
 return cb()
def provider_handler(cb: Callable[[], int]) -> int:
 try:
  raise IndexError()
 except IndexError:
  return cb()
'''
HANDLERS = '''def run(n: int) -> int:
 function_name_probe(); local_name_probe()
 try:
  raise ValueError()
 except ValueError:
  print(ail_reraise())
  try:
   rethrow()
  except ValueError:
   print("user name ValueError")
 try:
  rethrow()
 except RuntimeError:
  print("inactive")
 for i in range(n):
  try:
   raise KeyError()
  except KeyError:
   nested_handler()
   try:
    rethrow()
   except KeyError:
    print("restored KeyError")
 bad_bytes: bytes = b"\\xff"
 try:
  decoded: str = bad_bytes.decode()
 except ValueError:
  try:
   rethrow()
  except UnicodeDecodeError:
   print("original UnicodeDecodeError")
 try:
  rethrow()
 except RuntimeError:
  print("completed inactive")
 return 0
'''
FINALLY = '''def completed(mode: int) -> int:
 try:
  raise ValueError()
 except ValueError:
  if mode == 0:
   return 7
  print("handled")
 finally:
  try:
   rethrow()
  except RuntimeError:
   print("completed finally inactive")
 return 8
def pending() -> int:
 try:
  raise ValueError()
 finally:
  print(_ail_finally_cleanup1_handled())
  try:
   rethrow()
  except ValueError:
   print("pending ValueError")
 return 0
def inside() -> int:
 try:
  raise KeyError()
 except KeyError:
  try:
   print("inside")
  finally:
   rethrow()
 return 0
def suppressed() -> int:
 try:
  raise ValueError()
 finally:
  return 11
def overridden() -> int:
 try:
  raise ValueError()
 finally:
  raise IndexError()
 return 0
def loop(mode: int) -> int:
 total = 0
 for i in range(3):
  try:
   raise ValueError()
  except ValueError:
   total += 1
   if mode == 0:
    continue
   break
  finally:
   try:
    rethrow()
   except RuntimeError:
    print("loop finally inactive")
 return total
def run(n: int) -> int:
 print(completed(0)); print(completed(1))
 try:
  pending()
 except ValueError:
  print("propagated ValueError")
 try:
  inside()
 except KeyError:
  print("inside KeyError")
 print(suppressed())
 try:
  overridden()
 except IndexError:
  print("override IndexError")
 print(loop(0)); print(loop(1))
 try:
  print("normal")
 finally:
  try:
   rethrow()
  except RuntimeError:
   print("normal inactive")
 return 0
'''
OWNED = '''class Record:
 def __init__(self, value: int, text: str, data: bytes):
  self.value = value
  self.text = text
  self.data = data
def text_failure() -> str:
 scratch: str = "保持\\0😀" * 8193
 try:
  rethrow()
 finally:
  print("text finally")
 return scratch
def bytes_failure() -> bytes:
 scratch: bytes = b"\\0\\xff" * 8193
 rethrow()
 return scratch
def integers_failure() -> list[int]:
 scratch: list[int] = [i for i in range(8193)]
 rethrow()
 return scratch
def floats_failure() -> list[float]:
 scratch: list[float] = [float(i) for i in range(8193)]
 rethrow()
 return scratch
def record_failure(record: Record) -> Record:
 scratch = Record(record.value, "temporary", bytes(8193))
 try:
  rethrow()
 finally:
  record.value += 1
 return scratch
def run(n: int) -> int:
 text_cb: Callable[[], str] = text_failure
 bytes_cb: Callable[[], bytes] = bytes_failure
 ints_cb: Callable[[], list[int]] = integers_failure
 floats_cb: Callable[[], list[float]] = floats_failure
 record_cb: Callable[[Record], Record] = record_failure
 record = Record(7, "保持\\0😀", b"\\0\\xff")
 try:
  raise KeyError()
 except KeyError:
  try:
   text_cb()
  except KeyError:
   print("text KeyError")
  try:
   bytes_cb()
  except KeyError:
   print("bytes KeyError")
  try:
   ints_cb()
  except KeyError:
   print("ints KeyError")
  try:
   floats_cb()
  except KeyError:
   print("floats KeyError")
  try:
   record_cb(record)
  except KeyError:
   print("record KeyError")
 print(record.value); print(record.text.encode().hex()); print(record.data.hex())
 return 0
'''
CROSS = '''def caller_rethrow() -> int:
 raise
 return 0
def run(n: int) -> int:
 function_name_probe(); local_name_probe()
 try:
  raise KeyError()
 except KeyError:
  nested_handler()
  try:
   invoke(rethrow)
  except KeyError:
   print("caller to provider KeyError")
 try:
  provider_handler(caller_rethrow)
 except IndexError:
  print("provider to caller IndexError")
 try:
  rethrow()
 except RuntimeError:
  print("cross completed inactive")
 return 0
'''
RESOURCE = '''class Record:
 def __init__(self, value: int, text: str, data: bytes):
  self.value = value
  self.text = text
  self.data = data
def rethrow() -> int:
 raise
 return 0
def handler() -> int:
 scratch = Record(9, "discarded", bytes(8193))
 try:
  raise ValueError()
 except ValueError:
  try:
   rethrow()
  except ValueError:
   scratch.value += 1
 return scratch.value
def target(record: Record) -> Record:
 scratch: list[int] = [i for i in range(8193)]
 try:
  rethrow()
 finally:
  record.value += 1
 return record
def owned_text() -> str:
 scratch: str = "保持\\0😀" * 8193
 rethrow()
 return scratch
def owned_bytes() -> bytes:
 scratch: bytes = b"\\0\\xff" * 8193
 rethrow()
 return scratch
def owned_ints() -> list[int]:
 scratch: list[int] = [i for i in range(8193)]
 rethrow()
 return scratch
def owned_floats() -> list[float]:
 scratch: list[float] = [float(i) for i in range(8193)]
 rethrow()
 return scratch
def step(i: int) -> int:
 record = Record(i, "保持\\0😀", bytes(8193))
 cb: Callable[[Record], Record] = target
 text_cb: Callable[[], str] = owned_text
 bytes_cb: Callable[[], bytes] = owned_bytes
 ints_cb: Callable[[], list[int]] = owned_ints
 floats_cb: Callable[[], list[float]] = owned_floats
 try:
  raise KeyError()
 except KeyError:
  handler()
  try:
   cb(record)
  except KeyError:
   record.value += 2
  try:
   text_cb()
  except KeyError:
   record.value += 1
  try:
   bytes_cb()
  except KeyError:
   record.value += 1
  try:
   ints_cb()
  except KeyError:
   record.value += 1
  try:
   floats_cb()
  except KeyError:
   record.value += 1
 try:
  rethrow()
 except RuntimeError:
  record.value += 3
 return record.value + len(record.text) + len(record.data)
def run(n: int) -> int:
 total = 0
 for i in range(n):
  total += step(i)
 return total
'''


def expected(source,n=0):
    result,text,raw=callbacks.oracle(source,'run',n)
    if raw: raise AssertionError('unexpected oracle binary output')
    return result,text.encode()


def public_source(source):
    tree=ast.parse(source)
    classes=[node for node in tree.body if isinstance(node,ast.ClassDef)]
    if any(node.name!='Record' for node in classes): raise AssertionError('unexpected fixture class')
    header='struct Record { value:int; text:str; data:bytes; }\n' if classes else ''
    tree.body=[node for node in tree.body if not isinstance(node,ast.ClassDef)]
    return header+finally_support.brace_source(ast.unparse(tree))


class ReraiseTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def program_build(self,name,source):
        path=self.write(name+'.ail',public_source(source)+'\nfn main()->int { return run(int(sys.argv[1])); }'); out=self.root/name
        result=self.command('compile',path,'-o',out)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        path.unlink(); return out if out.exists() else out.with_suffix('.exe')

    def compare(self,exe,source,n=0):
        value,text=expected(source,n); result=subprocess.run([str(exe),str(n)],capture_output=True,timeout=180)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(value,text,b''))

    def test_original_class_nested_restore_inactive_and_301_rethrows(self):
        source=PROVIDER+HANDLERS
        exe=self.ail_build('handlers',finally_support.brace_source(source)+'\nfn main()->int { return run(int(sys.argv[1])); }')
        for n in (0,1,301,8193): self.compare(exe,source,n)

    def test_finally_pending_completed_return_loop_suppress_override(self):
        source=PROVIDER+FINALLY; exe=self.program_build('finally',source)
        self.compare(exe,source)

    def test_callback_owned_results_and_borrowed_struct_finally(self):
        source=PROVIDER+OWNED; exe=self.program_build('owned',source)
        self.compare(exe,source)

    def test_source_free_moved_objects_handled_context_both_directions(self):
        provider=self.ail_build('provider',finally_support.brace_source(PROVIDER),library=True)
        wrapper=self.ail_build('wrapper',finally_support.brace_source(CROSS),provider,library=True)
        destination=self.root/'移動😀 rethrow objects'; destination.mkdir(); objects=[]
        for obj in (provider,wrapper):
            moved=destination/obj.name
            shutil.move(str(obj),moved); shutil.move(str(obj)+'.json',str(moved)+'.json'); objects.append(moved)
        before=self.snapshot(*objects)
        exe=self.ail_build('entry','fn main()->int { return run(0); }',*objects)
        self.compare(exe,PROVIDER+CROSS); self.assertEqual(self.snapshot(*objects),before)

    def test_301_unwinds_live_zero_handled_zero_and_bounded_peak(self):
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            generated=to_c(translate(public_source(RESOURCE),module=True,imports=[]),name='run',strict=True)
        finally:
            sys.path.pop(0)
        drain='for(int64_t i=0;i<ail__blk_cache_n;i++) count_free(ail__blk_cache[i].p); ail__blk_cache_n=0;' if 'ail__blk_cache_n' in generated else ''
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in generated else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in generated else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host=r'''int main(int argc,char **argv) { int64_t r=run(strtoll(argv[1],NULL,10)); DRAIN
 fprintf(stderr,"{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"frames\":%d,\"handled\":%d}\n",(long long)r,live,live_bytes,peak_bytes,ail_cleanup_top!=NULL,ail_handled_code); return 0; }'''
        path=self.write('resources.c',ALLOCATOR+generated+host.replace('DRAIN',drain)); exe=self.root/('resources.exe' if os.name=='nt' else 'resources')
        cc=os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
        result=subprocess.run([cc,'-std=c11','-O2',str(path),'-lm','-o',str(exe)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')); peaks=[]
        for n in (31,301):
            value,text=expected(RESOURCE,n); self.assertEqual(text,b'')
            result=subprocess.run([str(exe),str(n)],capture_output=True,timeout=180)
            self.assertEqual((result.returncode,result.stdout),(0,b'')); metrics=json.loads(result.stderr)
            self.assertEqual((metrics['result'],metrics['live'],metrics['bytes'],metrics['frames'],metrics['handled']),(value,0,0,0,0)); peaks.append(metrics['peak'])
        self.assertLessEqual(peaks[1],peaks[0]*2+65536)

    def test_invalid_data_chaining_custom_handlers_still_refused(self):
        cases=('def run(n:int)->int:\n raise ValueError(1)\n',
               'def run(n:int)->int:\n raise ValueError() from None\n',
               'class Custom(Exception):\n pass\ndef run(n:int)->int:\n try:\n  raise ValueError()\n except Custom:\n  return 0\n return 0\n')
        for index,source in enumerate(cases):
            path=self.write('bad'+str(index)+'.py',source+'\ndef main()->int:\n return run(0)\nmain()\n'); out=self.root/('bad'+str(index))
            result=self.command('compile',path,'--syntax','python','-o',out)
            self.assertNotEqual(result.returncode,0,source); self.assertNotIn(b'Traceback',result.stderr)
            self.assertFalse(out.exists()); self.assertFalse(out.with_suffix('.exe').exists())


if __name__=='__main__': unittest.main()
