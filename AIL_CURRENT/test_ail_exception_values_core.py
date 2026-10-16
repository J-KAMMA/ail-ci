"""Built-in exception values preserve dynamic messages through ownership boundaries."""
import ast
import os
import shutil
import subprocess
import sys
import unittest

from ail_syntax import SyntaxErrorAIL, translate
import test_ail_c_objects as support


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'), 'installed C compiler required')
class ExceptionValueTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def test_dynamic_payload_nested_same_binding_and_caller_reraise(self):
        source = '''fn again() -> int { raise; return 0; }
fn main() -> int {
 try { raise ValueError("outer " + str(17) + " 日本😀"); }
 except ValueError as e {
  print(e.kind, e.message);
  try { raise KeyError("inner"); } except KeyError as e { print(e.kind, e.message); }
  print(e.kind, e.message);
  try { again(); } except ValueError as other { print(other.message); }
 }
 return 0;
}'''
        exe = self.ail_build('nested', source)
        self.check_run(exe, 'ValueError outer 17 日本😀\nKeyError inner\nValueError outer 17 日本😀\nouter 17 日本😀\n')

    def test_owned_escape_param_result_message_copy_and_finally(self):
        source = '''fn make(message: str) -> exception { return ValueError(message); }
fn keep(e: exception) -> exception { return e; }
fn caught() -> exception {
 try { raise make("escaped " + str(9)); }
 except ValueError as e { return keep(e); }
 finally { print("cleanup"); }
 return RuntimeError();
}
fn text() -> str { let e: exception = caught(); return e.message; }
fn main() -> int {
 let saved: exception = caught(); let copy: str = saved.message;
 saved = RuntimeError("replacement"); print(copy, text());
 try { raise keep(ValueError("forward")); } finally { print("final"); }
 return 0;
}'''
        exe = self.ail_build('escape', source)
        result = subprocess.run([str(exe)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.replace(b'\r\n', b'\n'), b'cleanup\ncleanup\nescaped 9 escaped 9\nfinal\n')
        self.assertEqual(result.stderr.replace(b'\r\n', b'\n'), b'ValueError: forward\n')

    def test_unmatched_payload_finally_replacement_legacy_trap(self):
        source = '''fn forwarded() -> int {
 try { try { raise OSError("元😀"); } except KeyError { return 8; } }
 finally { print("forward cleanup"); }
 return 0;
}
fn replaced() -> int {
 try { raise ValueError("discarded"); } finally { raise IndexError("replacement"); }
 return 0;
}
fn main() -> int {
 try { forwarded(); } except OSError as e { print(e.message); }
 try { replaced(); } except IndexError as e { print(e.message); }
 try { try { int("bad"); } except KeyError { return 8; } }
 except ValueError as e { print(e.kind, len(e.message)); }
 return 0;
}'''
        exe = self.ail_build('propagation', source)
        self.check_run(exe, 'forward cleanup\n元😀\nreplacement\nValueError 0\n')

    def test_cross_object_exception_param_result_and_dynamic_reraise(self):
        library = self.ail_build('provider', '''fn make(s: str) -> exception { return OSError(s); }
fn keep(e: exception) -> exception { return e; }
fn again() -> int { raise; return 0; }''', library=True)
        exe = self.ail_build('consumer', '''fn main() -> int {
 let value: exception = keep(make("跨 object😀"));
 try { raise value; } except OSError as e {
  try { again(); } except OSError as other { print(other.kind, other.message); }
 }
 return 0;
}''', library)
        self.check_run(exe, 'OSError 跨 object😀\n')

    def test_payload_allocator_zero_live_and_bounded_loop_peak(self):
        from test_ail_exception_resources import ExceptionResourceTests
        native = '''def make(message: str) -> exception:
 return ValueError(message)
def keep(e: exception) -> exception:
 return e
def caught(i: int) -> exception:
 try:
  raise make("日本😀" + str(i))
 except ValueError as e:
  return keep(e)
 finally:
  scratch = "cleanup" + str(i)
 return RuntimeError()
def run(n: int) -> int:
 total = 0
 saved = ValueError("seed")
 for i in range(n):
  saved = caught(i)
  message = saved.message
  try:
   try:
    raise saved
   finally:
    if i % 3 == 0:
     raise KeyError("replaced" + str(i))
  except (ValueError, KeyError) as e:
   total += len(e.message) + len(message)
 return total
'''
        # AIL message is the raw constructor argument, including for KeyError whose
        # CPython str(error) adds quotes. The independent reference reads args directly.
        reference = native.replace(' -> exception', '').replace(': exception', '').replace('saved.message', 'saved.args[0]').replace('e.message', 'e.args[0]')
        verifier = ExceptionResourceTests()
        verifier.check_resources(reference, sizes=(1, 2, 101, 1001), native_source=native)
    def test_exception_fields_and_lists_share_ownership_on_alias_and_mutation(self):
        source = '''struct Box { error:exception; errors:list[exception]; }
fn keep(values:list[exception]) -> list[exception] { return values; }
fn read(box:Box) -> exception { return box.error; }
fn main() -> int {
 let values:list[exception]=[ValueError("日本😀"),KeyError("old")];
 let alias=keep(values); let box=Box(values[0],values);
 box.error=read(box); values[0]=values[0];
 let saved=alias.pop(); box.errors.append(box.error);
 box.error=OSError("new"); box.errors[0]=box.error;
 for item in box.errors { print(item.kind,item.message); }
 print(saved.kind,saved.message); let copy=list(values); values.clear();
 try { raise copy[-1]; } except ValueError as e { print(e.message); }
 copy.clear(); return 0;
}'''
        exe = self.ail_build('containers', source)
        self.check_run(exe, 'OSError new\nValueError 日本😀\nKeyError old\n日本😀\n')

    def test_exception_container_allocator_alias_finally_and_partial_constructor(self):
        from test_ail_exception_resources import ExceptionResourceTests
        native = '''class Box:
 def __init__(self, error:exception, errors:list[exception], number:str):
  self.error=error
  self.errors=errors
  self.number=int(number)
def keep(values:list[exception])->list[exception]:
 return values
def get(box:Box)->exception:
 return box.error
def made(i:int)->Box:
 values:list[exception]=[ValueError("日本😀"+str(i)),KeyError("key"+str(i))]
 return Box(values[0],keep(values),str(i))
def run(n:int)->int:
 total=0
 for i in range(n):
  box=made(i)
  alias=keep(box.errors)
  box.error=get(box)
  alias[0]=alias[0]
  popped=alias.pop()
  alias.append(box.error)
  alias.extend(alias)
  copy=list(alias)
  alias.clear()
  box.errors=copy
  box.error=OSError("next"+str(i))
  try:
   try:
    raise box.errors[-1]
   finally:
    if i%3==0:
     raise box.error
  except (ValueError,OSError) as caught:
   total+=len(caught.message)+len(popped.message)
  for error in box.errors:
   total+=len(error.message)
  box.errors.clear()
  try:
   broken=Box(ValueError("partial"),[KeyError("owned")],"bad")
  except ValueError:
   total+=1
 return total
'''
        reference=native.replace('exception','BaseException').replace('.message','.args[0]')
        ExceptionResourceTests().check_resources(reference,sizes=(1,2,101,1001),native_source=native)
    def test_exception_callbacks_source_free_alias_returns_and_fields(self):
        provider = self.ail_build('callback_provider', '''fn identity_exception(e:exception)->exception {return e;}
fn identity_errors(values:list[exception])->list[exception] {return values;}
fn failed(e:exception)->exception {raise e; return e;}
fn get_one()->Callable[[exception],exception] {return identity_exception;}
fn get_many()->Callable[[list[exception]],list[exception]] {return identity_errors;}
fn get_failed()->Callable[[exception],exception] {return failed;}''', library=True)
        consumer = '''struct Callbacks {one:Callable[[exception],exception]; many:Callable[[list[exception]],list[exception]];}
fn apply(cb:Callable[[exception],exception],e:exception)->exception {return cb(e);}
fn main()->int {
 let callbacks=Callbacks(get_one(),get_many());
 let value=callbacks.one(ValueError("callback 日本😀"));
 let values:list[exception]=[value]; let alias=callbacks.many(values);
 let saved=apply(callbacks.one,alias[0]); values[0]=saved; alias[0]=alias[0];
 let message=saved.message; alias.clear(); print(saved.kind,message,len(values));
 callbacks.one=get_failed();
 try { callbacks.one(saved); } except ValueError as e {print(e.message);}
 return 0;
}'''
        exe = self.ail_build('callback_consumer', consumer, provider)
        self.check_run(exe, 'ValueError callback 日本😀 0\ncallback 日本😀\n')

    def test_exception_callback_allocator_owned_return_and_raise(self):
        from test_ail_exception_resources import ExceptionResourceTests
        native = '''class Callbacks:
 def __init__(self, one:Callable[[exception],exception], many:Callable[[list[exception]],list[exception]]):
  self.one=one
  self.many=many
def one(e:exception)->exception:
 return e
def many(values:list[exception])->list[exception]:
 return values
def failed(e:exception)->exception:
 raise e
 return e
def apply(cb:Callable[[exception],exception],e:exception)->exception:
 return cb(e)
def run(n:int)->int:
 total=0
 callbacks=Callbacks(one,many)
 for i in range(n):
  callbacks.one=one
  value=callbacks.one(ValueError("callback 日本😀"+str(i)))
  values:list[exception]=[value]
  alias=callbacks.many(values)
  saved=apply(callbacks.one,alias[0])
  values[0]=saved
  alias[0]=alias[0]
  message=saved.message
  alias.clear()
  total+=len(message)
  callbacks.one=failed
  try:
   callbacks.one(saved)
  except ValueError as error:
   total+=len(error.message)
 return total
'''
        from test_ail_callable_values import oracle_source
        reference=oracle_source(native).replace('.message','.args[0]')
        ExceptionResourceTests().check_resources(reference,sizes=(1,2,101,1001),native_source=native)
    def test_bad_message_fields_binding_scope_and_custom_types_refused(self):
        cases = ('raise ValueError(1);', 'raise ValueError(message="bad");',
                 'raise ValueError("a", "b");',
                 'try {raise ValueError();} except ValueError as e { print(e.kind); } print(e.message);',
                 'try {raise ValueError();} except ValueError as e { e.message = "bad"; }',
                 'raise UnknownError();', 'raise ValueError() from KeyError();')
        for index, body in enumerate(cases):
            with self.subTest(body=body):
                path = self.write('bad%d.ail' % index, 'fn main() -> int {' + body + 'return 0;}')
                result = self.command('check', path)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn(b'Traceback', result.stdout + result.stderr)


class ExceptionValueNameTests(unittest.TestCase):
    def test_exception_callback_signature_roundtrip_and_c_declarations(self):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            import callable_types
            for text, element, c_element in (
                    ('Callable[[exception], exception]', 'exception', 'ail_exception *'),
                    ('Callable[[list[exception]], list[exception]]', 'handle_list:exception', 'ail_hlist_exception *')):
                with self.subTest(text=text):
                    kind=callable_types.parse(ast.parse(text,mode='eval').body)
                    self.assertEqual(callable_types.unpack(kind),((element,),element))
                    self.assertEqual(callable_types.annotation(kind),text)
                    self.assertIn(c_element,callable_types.declaration(kind))
                    self.assertEqual(callable_types.parse(ast.parse(callable_types.annotation(kind),mode='eval').body),kind)
        finally:
            sys.path.pop(0)

    def test_tuple_handler_binding_token_boundary(self):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            cases = ('ValueError as e', '(ValueError,OSError) as e',
                     '(ValueError,OSError)as e', '(ValueError, OSError, KeyError) as e',
                     '(ValueError, OSError, KeyError)as e')
            for handler in cases:
                with self.subTest(handler=handler):
                    source = 'fn main()->int {try {raise ValueError("bad");} except ' + handler + ' {print(e.message);} return 0;}'
                    to_c(translate(source), name='run', strict=True)
            with self.assertRaisesRegex(SyntaxErrorAIL, 'unsupported block header'):
                translate('fn main()->int {try {raise ValueError();} except ValueErroras e {return 1;} return 0;}')
        finally:
            sys.path.pop(0)


    def test_unsupported_exception_container_shapes_are_refused(self):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfront import Unsupported
            from pyfunc import to_c
            cases = ('let values=(ValueError("bad"),1);',
                     'let values={1:ValueError("bad")};',
                     'let values={ValueError("bad")};',
                     'let values=[[ValueError("bad")]];',
                     'let values=[ValueError("bad"),1];',
                     'let values:list[exception]=[]; values.append(1);',
                     'let values:list[exception]=[]; values[0]=1;',
                     'let values:list[exception]=[]; values.pop(1.0);')
            for body in cases:
                with self.subTest(body=body), self.assertRaises(Unsupported):
                    to_c(translate('fn main()->int {' + body + 'return 0;}'), name='run', strict=True)
        finally:
            sys.path.pop(0)


    def test_builtin_exception_type_names_are_reserved(self):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from module_object import typed_module, _valid_name
            from pyfront import Unsupported
            from pyfunc import to_c
            with self.assertRaisesRegex(SyntaxErrorAIL, 'reserved struct name: exception'):
                translate('struct exception { value: int; } fn main()->int {return 0;}')
            legacy = 'class exception:\n def __init__(self,value:int):\n  self.value=value\ndef read(e:exception)->int:\n return e.value\ndef main()->int:\n return read(exception(1))\nmain()\n'
            with self.assertRaisesRegex(Unsupported, 'reserved class name: exception'):
                to_c(legacy, name='run', strict=True)
            with self.assertRaisesRegex(Unsupported, 'reserved builtin name: exception'):
                typed_module('def exception()->int:\n return 1\n')
            self.assertFalse(_valid_name('exception'))
        finally:
            sys.path.pop(0)


if __name__ == '__main__':
    unittest.main()