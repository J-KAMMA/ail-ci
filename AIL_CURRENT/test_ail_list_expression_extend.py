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
    source=oracle_source(source).replace(".message",".args[0]")
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


WHOLE='from ail import write_stdout_bytes\nimport sys\n\ndef integers(n: int) -> list[int]:\n    print(\'i\', n)\n    return [n, n + 1]\n\ndef floating(n: int) -> list[float]:\n    print(\'f\', n)\n    return [float(n), float(n) + 0.5]\n\ndef strings(n: int) -> list[str]:\n    print(\'s\', n)\n    return [\'日本😀\' + str(n), \'end\']\n\ndef blobs(n: int) -> list[bytes]:\n    print(\'b\', n)\n    return [b\'\\x00\\xff\', bytes([n])]\n\ndef fail() -> list[int]:\n    scratch = [4, 5]\n    raise ValueError(\'source\')\n    return scratch\n\ndef main() -> int:\n    ints = [7]\n    floats = [7.5]\n    texts = [\'seed\']\n    binary: list[bytes] = [b\'x\']\n    ci: Callable[[int], list[int]] = integers\n    cf: Callable[[int], list[float]] = floating\n    cs: Callable[[int], list[str]] = strings\n    cb: Callable[[int], list[bytes]] = blobs\n    ints.extend(integers(1))\n    floats.extend(floating(1))\n    texts.extend(strings(1))\n    binary.extend(blobs(1))\n    ints.extend(ci(2))\n    floats.extend(cf(2))\n    texts.extend(cs(2))\n    binary.extend(cb(2))\n    ints.extend(integers(3) if True else integers(4))\n    floats.extend(floating(3) if False else floating(4))\n    texts.extend(strings(3) if True else strings(4))\n    binary.extend(blobs(3) if False else blobs(4))\n    ints.extend(ints[::-2])\n    floats.extend(floats[:2])\n    texts.extend(texts[::-2])\n    binary.extend(binary[:2])\n    ints.extend(ints)\n    floats.extend(floats)\n    texts.extend(texts)\n    binary.extend(binary)\n    try:\n        texts.extend(texts[::0])\n    except ValueError:\n        print(\'zero-step\')\n    ints.extend(ints[::-9223372036854775808])\n    floats.extend(floats[::-9223372036854775808])\n    texts.extend(texts[::-9223372036854775808])\n    binary.extend(binary[::-9223372036854775808])\n    try:\n        ints.extend(fail())\n    except ValueError as e:\n        print(e.message)\n    finally:\n        print(\'cleanup\')\n    try:\n        ints.extend([int(\'1\'), int(\'bad\')])\n    except ValueError:\n        print(\'partial\')\n    for i in ints:\n        print(i)\n    for f in floats:\n        print(f)\n    for s in texts:\n        print(s)\n    for b in binary:\n        write_stdout_bytes(b)\n        write_stdout_bytes(b\'|\')\n    print()\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

FIELDS='from ail import write_stdout_bytes\nimport sys\n\nclass Box:\n\n    def __init__(self, ints: list[int], floats: list[float], binary: list[bytes], strings: list[str]):\n        self.ints = ints\n        self.floats = floats\n        self.binary = binary\n        self.strings = strings\n\ndef owner(box: Box) -> Box:\n    print(\'receiver\')\n    return box\n\ndef changed_i(box: Box) -> list[int]:\n    print(\'source\')\n    box.ints = [20, 21]\n    return box.ints\n\ndef changed_f(box: Box) -> list[float]:\n    print(\'source-f\')\n    for index in range(17):\n        box.floats.append(float(index) + 0.5)\n    return box.floats\n\ndef changed_b(box: Box) -> list[bytes]:\n    print(\'source-b\')\n    box.binary = [b\'new\']\n    return [b\'tail\']\n\ndef main() -> int:\n    box = Box([1], [1.5], [b\'old\'], [\'snapshot\'])\n    owner(box).ints.extend(changed_i(box))\n    owner(box).floats.extend(changed_f(box))\n    old = box.binary\n    owner(box).binary.extend(changed_b(box))\n    text: list[str] = box.strings\n    text.extend([\'local\'])\n    for i in box.ints:\n        print(i)\n    for f in box.floats:\n        print(f)\n    for b in old:\n        write_stdout_bytes(b)\n        write_stdout_bytes(b\'|\')\n    print()\n    for b in box.binary:\n        write_stdout_bytes(b)\n        write_stdout_bytes(b\'|\')\n    print()\n    for s in box.strings:\n        print(s)\n    for s in text:\n        print(s)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


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
        provider=self.ail_build('provider',"def ints() -> list[int]:\n    return [1, 2]\n\ndef floats() -> list[float]:\n    return [1.5, 2.5]\n\ndef texts() -> list[str]:\n    return ['日本😀', 'text']\n\ndef binary() -> list[bytes]:\n    return [b'\\x00\\xff', b'b']\n\ndef ci() -> Callable[[], list[int]]:\n    return ints\n\ndef cf() -> Callable[[], list[float]]:\n    return floats\n\ndef cs() -> Callable[[], list[str]]:\n    return texts\n\ndef cb() -> Callable[[], list[bytes]]:\n    return binary\n\ndef keep_text(values: list[str]) -> list[str]:\n    return values\n\ndef keep_binary(values: list[bytes]) -> list[bytes]:\n    return values\n\ndef cts() -> Callable[[list[str]], list[str]]:\n    return keep_text\n\ndef cbs() -> Callable[[list[bytes]], list[bytes]]:\n    return keep_binary\n",library=True)
        consumer='from ail import write_stdout_bytes\nimport sys\n\ndef main() -> int:\n    i: list[int] = []\n    f: list[float] = []\n    s: list[str] = []\n    b: list[bytes] = []\n    fi = ci()\n    ff = cf()\n    fs = cs()\n    fb = cb()\n    i.extend(fi())\n    f.extend(ff())\n    s.extend(fs())\n    b.extend(fb())\n    ts = cts()\n    bs = cbs()\n    s.extend(ts(s))\n    b.extend(bs(b))\n    saved_s = ts(s)\n    saved_b = bs(b)\n    s.clear()\n    s = [\'replacement\']\n    b = [b\'replacement\']\n    s.extend(saved_s)\n    b.extend(saved_b)\n    for xi in i:\n        print(xi)\n    for xf in f:\n        print(xf)\n    for xs in s:\n        print(xs)\n    for xb in b:\n        write_stdout_bytes(xb)\n        write_stdout_bytes(b\'|\')\n    print()\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'
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
        cases=('import sys\n\ndef bad(values: list[float]) -> int:\n    values.extend([1.5])\n    return 0\n\ndef main() -> int:\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
               'import sys\n\ndef bad(values: list[str]) -> int:\n    values.extend([\'a\'])\n    return 0\n\ndef main() -> int:\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
               'import sys\n\ndef main() -> int:\n    values: list[int] = []\n    values.extend([1.5])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
               'import sys\n\ndef main() -> int:\n    values: list[float] = []\n    values.extend([1])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
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