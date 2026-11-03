"""Scalar-list expressions extend once in order with owned snapshots and field-slot semantics."""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_c_objects as support
import test_ail_source_check as checks
from test_ail_callable_values import oracle_source


def reference(source, *, cells=False):
    source=oracle_source(translate(source)).replace(".message",".args[0]")
    if cells:
        class Slots(ast.NodeTransformer):
            def visit_Assign(self,node):
                self.generic_visit(node)
                if isinstance(node.value,ast.Attribute) and node.value.attr=='strings':
                    node.value=ast.Call(func=ast.Name(id='list',ctx=ast.Load()),args=[node.value],keywords=[])
                return node
            def visit_Call(self,node):
                self.generic_visit(node)
                if (isinstance(node.func,ast.Attribute) and node.func.attr=='extend'
                        and isinstance(node.func.value,ast.Attribute)
                        and node.func.value.attr in ('ints','floats')):
                    owner=node.func.value.value
                    lazy=ast.Lambda(args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=node.args[0])
                    return ast.copy_location(ast.Call(func=ast.Name(id='slot_extend',ctx=ast.Load()),args=[owner,ast.Constant(node.func.value.attr),lazy],keywords=[]),node)
                return node
        source=ast.unparse(ast.fix_missing_locations(Slots().visit(ast.parse(source))))
    prefix='''import sys

def write_stdout_bytes(data):
 sys.stdout.flush()
 sys.stdout.buffer.write(data)
 sys.stdout.buffer.flush()

def slot_extend(owner,field,source):
 values=source()
 getattr(owner,field).extend(values)
'''
    result=subprocess.run([sys.executable,'-X','utf8','-B','-c',prefix+source+'\nraise SystemExit(main())\n'],capture_output=True,timeout=30)
    if result.returncode: raise AssertionError(result.stderr.decode(errors='replace'))
    return result.stdout.replace(b'\r\n',b'\n')


WHOLE='''fn integers(n:int)->list[int] {print("i",n);return [n,n+1];}
fn floating(n:int)->list[float] {print("f",n);return [float(n),float(n)+0.5];}
fn strings(n:int)->list[str] {print("s",n);return ["日本😀"+str(n),"end"] ;}
fn blobs(n:int)->list[bytes] {print("b",n);return [b"\\x00\\xff",bytes([n])];}
fn fail()->list[int] {let scratch=[4,5];raise ValueError("source");return scratch;}
fn main()->int {
 let ints=[7]; let floats=[7.5]; let texts=["seed"]; let binary:list[bytes]=[b"x"];
 let ci:Callable[[int],list[int]]=integers; let cf:Callable[[int],list[float]]=floating;
 let cs:Callable[[int],list[str]]=strings; let cb:Callable[[int],list[bytes]]=blobs;
 ints.extend(integers(1)); floats.extend(floating(1));texts.extend(strings(1));binary.extend(blobs(1));
 ints.extend(ci(2));floats.extend(cf(2));texts.extend(cs(2));binary.extend(cb(2));
 ints.extend(integers(3) if true else integers(4));floats.extend(floating(3) if false else floating(4));
 texts.extend(strings(3) if true else strings(4));binary.extend(blobs(3) if false else blobs(4));
 ints.extend(ints[::-2]);floats.extend(floats[:2]);texts.extend(texts[::-2]);binary.extend(binary[:2]);
 ints.extend(ints);floats.extend(floats);texts.extend(texts);binary.extend(binary);
 try {texts.extend(texts[::0]);} except ValueError {print("zero-step");}
 ints.extend(ints[::-9223372036854775808]);floats.extend(floats[::-9223372036854775808]);
 texts.extend(texts[::-9223372036854775808]);binary.extend(binary[::-9223372036854775808]);
 try {ints.extend(fail());} except ValueError as e {print(e.message);} finally {print("cleanup");}
 try {ints.extend([int("1"),int("bad")]);} except ValueError {print("partial");}
 for i in ints {print(i);} for f in floats {print(f);} for s in texts {print(s);}
 for b in binary {write_stdout_bytes(b);write_stdout_bytes(b"|");} print();
 return 0;
}'''

FIELDS='''struct Box {ints:list[int];floats:list[float];binary:list[bytes];strings:list[str];}
fn owner(box:Box)->Box {print("receiver");return box;}
fn changed_i(box:Box)->list[int] {print("source");box.ints=[20,21];return box.ints;}
fn changed_f(box:Box)->list[float] {print("source-f");for index in range(17) {box.floats.append(float(index)+0.5);}return box.floats;}
fn changed_b(box:Box)->list[bytes] {print("source-b");box.binary=[b"new"];return [b"tail"] ;}
fn main()->int {
 let box=Box([1],[1.5],[b"old"],["snapshot"]);
 owner(box).ints.extend(changed_i(box));owner(box).floats.extend(changed_f(box));
 let old=box.binary;owner(box).binary.extend(changed_b(box));
 let text:list[str]=box.strings;text.extend(["local"]);
 for i in box.ints {print(i);} for f in box.floats {print(f);}
 for b in old {write_stdout_bytes(b);write_stdout_bytes(b"|");}print();
 for b in box.binary {write_stdout_bytes(b);write_stdout_bytes(b"|");}print();
 for s in box.strings {print(s);} for s in text {print(s);}return 0;
}'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class ListExpressionExtendTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build

    def assert_run(self,source,*,cells=False):
        expected=reference(source,cells=cells)
        binary=self.ail_build('extend',source)
        result=subprocess.run([str(binary)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,expected,b''))

    def test_four_type_whole_output_source_once_self_slice_finally_partial_throw(self):
        self.assert_run(WHOLE)

    def test_receiver_capture_numeric_field_slots_and_bytes_identity(self):
        # SEM 113 declares numeric fields as slots; the independent Python Cell adapter
        # captures the owner before evaluating the source, then mutates the current slot.
        self.assert_run(FIELDS,cells=True)

    def test_source_free_owned_callback_returns_for_four_list_types(self):
        provider=self.ail_build('provider','''fn ints()->list[int] {return [1,2];}
fn floats()->list[float] {return [1.5,2.5];}
fn texts()->list[str] {return ["日本😀","text"];}
fn binary()->list[bytes] {return [b"\\x00\\xff",b"b"];}
fn ci()->Callable[[],list[int]] {return ints;}
fn cf()->Callable[[],list[float]] {return floats;}
fn cs()->Callable[[],list[str]] {return texts;}
fn cb()->Callable[[],list[bytes]] {return binary;}
fn keep_text(values:list[str])->list[str] {return values;}
fn keep_binary(values:list[bytes])->list[bytes] {return values;}
fn cts()->Callable[[list[str]],list[str]] {return keep_text;}
fn cbs()->Callable[[list[bytes]],list[bytes]] {return keep_binary;}''',library=True)
        consumer='''fn main()->int {
 let i:list[int]=[];let f:list[float]=[];let s:list[str]=[];let b:list[bytes]=[];
 let fi=ci();let ff=cf();let fs=cs();let fb=cb();
 i.extend(fi());f.extend(ff());s.extend(fs());b.extend(fb());
 let ts=cts();let bs=cbs();s.extend(ts(s));b.extend(bs(b));
 let saved_s=ts(s);let saved_b=bs(b);s.clear();s=["replacement"];b=[b"replacement"];
 s.extend(saved_s);b.extend(saved_b);
 for xi in i {print(xi);}for xf in f {print(xf);}for xs in s {print(xs);}for xb in b {write_stdout_bytes(xb);write_stdout_bytes(b"|");}print();return 0;
}'''
        binary=self.ail_build('consumer',consumer,provider)
        result=subprocess.run([str(binary)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,'1\n2\n1.5\n2.5\nreplacement\n日本😀\ntext\n日本😀\ntext\n'.encode()+b'replacement|\x00\xff|b|\x00\xff|b|\n',b''))

    def test_allocator_return_lifetimes_throw_and_repeated_reallocation(self):
        from test_ail_exception_resources import ExceptionResourceTests
        native='''def ints(n:int)->list[int]:
 try:
  return [n,n+1]
 finally:
  marker=n+3
def floats(n:int)->list[float]:
 return [float(n),float(n)+0.5]
def texts(n:int)->list[str]:
 return ["日本😀"+str(n),"text"]
def binary(n:int)->list[bytes]:
 return [b"\\x00\\xff",bytes([n%256])]
def failed()->list[int]:
 scratch=[1,2,3]
 raise ValueError()
 return scratch
def run(n:int)->int:
 total=0
 ci:Callable[[int],list[int]]=ints
 cf:Callable[[int],list[float]]=floats
 cs:Callable[[int],list[str]]=texts
 cb:Callable[[int],list[bytes]]=binary
 for j in range(n):
  i:list[int]=[7]
  f:list[float]=[7.5]
  s:list[str]=["seed"]
  b:list[bytes]=[b"x"]
  i.extend(ci(j))
  f.extend(cf(j))
  s.extend(cs(j))
  b.extend(cb(j))
  i.extend(i[::-1])
  f.extend(f[:1])
  s.extend(s[::-1])
  b.extend(b[:1])
  try:
   i.extend(failed())
  except ValueError:
   total+=len(i)
  for iv in i:
   total+=iv
  for fv in f:
   total+=int(fv*2.0)
  for sv in s:
   total+=len(sv)
  for bv in b:
   total+=len(bv)+bv[0]
 return total
'''
        ExceptionResourceTests().check_resources(oracle_source(native),sizes=(1,2,101,1001),native_source=native)


class ListExpressionExtendTypeTests(unittest.TestCase):
    setUp=checks.SourceCheckTests.setUp
    source=checks.SourceCheckTests.source
    check=checks.SourceCheckTests.check

    def test_readonly_parameters_snapshot_fields_and_wrong_widths_stay_refused(self):
        cases=('fn bad(values:list[float])->int {values.extend([1.5]);return 0;} fn main()->int {return 0;}',
               'fn bad(values:list[str])->int {values.extend(["a"]);return 0;} fn main()->int {return 0;}',
               'fn main()->int {let values:list[int]=[];values.extend([1.5]);return 0;}',
               'fn main()->int {let values:list[float]=[];values.extend([1]);return 0;}')
        for text in cases:
            with self.subTest(text=text):
                status,report=self.check(self.source(text))
                self.assertEqual(status,1,report)

    def test_slice_zero_step_and_int64_extremes_are_type_checked(self):
        for kind,values in [('int','[1]'),('float','[1.5]'),('str','["a"]'),('bytes','[b"a"]')]:
            with self.subTest(kind=kind):
                status,report=self.check(self.source('fn main()->int {let values:list['+kind+']='+values+';try {values.extend(values[::0]);} except ValueError {} values.extend(values[::-9223372036854775808]);return 0;}'))
                self.assertEqual(status,0,report)


if __name__=='__main__':unittest.main()