"""Packed string-field slot mutation compared with an independent Python Cell profile."""
import ast
import os
import shutil
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_c_objects as support
import test_ail_source_check as checks
from test_ail_callable_values import oracle_source


def cell_reference(source):
    """Declared field profile: owner first, RHS then bounds, mutate current slot; reads snapshot."""
    tree=ast.parse(oracle_source(source))
    def thunk(value):
        return ast.Lambda(args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=value)
    def index(value):
        if isinstance(value,ast.Slice):
            return ast.Call(func=ast.Name(id='slice',ctx=ast.Load()),args=[part if part is not None else ast.Constant(None) for part in (value.lower,value.upper,value.step)],keywords=[])
        return value
    def field(value):
        return isinstance(value,ast.Attribute) and value.attr=='values'
    class Slots(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Attribute) and field(node.func.value) and node.func.attr in ('append','extend','pop','clear','reverse','sort'):
                owner=self.visit(node.func.value.value)
                args=ast.Tuple(elts=[self.visit(value) for value in node.args],ctx=ast.Load())
                return ast.copy_location(ast.Call(func=ast.Name(id='slot_call',ctx=ast.Load()),args=[owner,ast.Constant(node.func.attr),thunk(args)],keywords=[]),node)
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript) and field(node.targets[0].value):
                target=node.targets[0]
                return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Name(id='slot_store',ctx=ast.Load()),args=[self.visit(target.value.value),thunk(self.visit(index(target.slice))),thunk(self.visit(node.value))],keywords=[])),node)
            self.generic_visit(node)
            if field(node.value):
                node.value=ast.Call(func=ast.Name(id='list',ctx=ast.Load()),args=[node.value],keywords=[])
            return node
        def visit_AugAssign(self,node):
            if field(node.target) and isinstance(node.op,ast.Add):
                return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Name(id='slot_call',ctx=ast.Load()),args=[self.visit(node.target.value),ast.Constant('extend'),thunk(ast.Tuple(elts=[self.visit(node.value)],ctx=ast.Load()))],keywords=[])),node)
            return self.generic_visit(node)
        def visit_Delete(self,node):
            target=node.targets[0]
            if isinstance(target,ast.Subscript) and field(target.value):
                return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Name(id='slot_delete',ctx=ast.Load()),args=[self.visit(target.value.value),thunk(self.visit(index(target.slice)))],keywords=[])),node)
            return self.generic_visit(node)
        def visit_For(self,node):
            self.generic_visit(node)
            if field(node.iter):
                node.iter=ast.Call(func=ast.Name(id='list',ctx=ast.Load()),args=[node.iter],keywords=[])
            return node
    text=ast.unparse(ast.fix_missing_locations(Slots().visit(tree)))
    prefix='''
def slot_call(owner,method,args):
 values=args()
 if method=='extend': values=(list(values[0]),)
 return getattr(owner.values,method)(*values)
def slot_store(owner,index,value):
 rhs=value()
 where=index()
 owner.values[where]=rhs
def slot_delete(owner,index):
 where=index()
 del owner.values[where]
'''
    return prefix+text


WHOLE='''struct Box {values:list[str];}
fn owner(box:Box)->Box {print("owner");return box;}
fn changed(box:Box)->list[str] {print("source");box.values=["new","日本😀"];return box.values;}
fn changed_text(box:Box)->str {print("text");box.values=["replaced","tail"];return "値\\x00😀";}
fn bound(box:Box)->int {print("bound");box.values.append("bound-tail");return -1;}
fn failed()->list[str] {let partial=["allocated","日本😀"];raise ValueError();return partial;}
fn main()->int {
 let box=Box(["old","a\\x00b","😀","終"]);let old=box.values;
 owner(box).values.extend(changed(box));let saved=box.values.pop();box.values.append(saved);
 owner(box).values[bound(box)]=changed_text(box);
 box.values[1:1]=["insert1","insert2"];box.values[3:1]=["empty-span"];
 box.values[::-1]=box.values;box.values.reverse();box.values.sort();
 let popped=box.values.pop(-2);box.values+=["end"];let before=box.values;
 try {box.values.extend(failed());} except ValueError {print("throw");} finally {print("finally");}
 try {box.values.extend(["partial",str(int("bad"))]);} except ValueError {print("partial");}
 try {box.values[::2]=["wrong"]; } except ValueError {print("mismatch");}
 try {del box.values[::0];} except ValueError {print("zero-step");}
 try {box.values[9223372036854775807]="bad";} except IndexError {print("index");}
 del box.values[::-9223372036854775808];del box.values[::2];
 for value in box.values {print(len(value),value);box.values.clear();}
 try {box.values.pop();} except IndexError {print("empty-pop");}
 try {box.values[-9223372036854775808]="bad";} except IndexError {print("min-index");}
 print("old");for first in old {print(len(first),first);}
 print("before");for second in before {print(len(second),second);}
 print("pop",len(popped),popped);print("saved",len(saved),saved);return 0;
}'''


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class StringFieldMutationTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build

    def test_whole_output_slot_order_snapshots_unicode_bounds_and_failures(self):
        text=cell_reference(translate(WHOLE))+'\nraise SystemExit(main())\n'
        expected=subprocess.run([sys.executable,'-X','utf8','-B','-c',text],capture_output=True,timeout=30)
        self.assertEqual(expected.returncode,0,expected.stderr)
        binary=self.ail_build('strings',WHOLE)
        actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
        self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),
                         (0,expected.stdout.replace(b'\r\n',b'\n'),b''))

    def test_source_free_provider_callback_rhs_and_owned_pop_return(self):
        provider=self.ail_build('provider','''struct Box {values:list[str];}
fn make()->Box {return Box(["source-free","日本😀"]);}
fn incoming()->list[str] {return ["callback","tail"];}
fn callback()->Callable[[],list[str]] {return incoming;}
fn changed(box:Box)->str {box.values.reverse();return box.values.pop();}
fn callback_text()->Callable[[Box],str] {return changed;}
fn take(box:Box)->str {try {return box.values.pop();} finally {box.values.clear();}}''',library=True)
        consumer='''fn main()->int {let box=make();let cb=callback();let ct=callback_text();
 box.values.extend(cb());box.values[0]=ct(box);let old=box.values;let popped=take(box);box.values.append("new");
 for value in old {print(value);}print("pop",popped);for next in box.values {print(next);}return 0;}'''
        binary=self.ail_build('consumer',consumer,provider)
        actual=subprocess.run([str(binary)],capture_output=True,timeout=30)
        self.assertEqual((actual.returncode,actual.stdout.replace(b'\r\n',b'\n'),actual.stderr),
                         (0,'source-free\ncallback\n日本😀\npop 日本😀\nnew\n'.encode(),b''))

    def test_allocator_repack_self_overlap_finally_and_partial_source_cleanup(self):
        from test_ail_exception_resources import ExceptionResourceTests
        native=translate('''struct Box {values:list[str];}
fn incoming(n:int)->list[str] {return ["日本😀"+str(n),"a\\x00b"];}
fn failed()->list[str] {let scratch=["partial","😀"];raise ValueError();return scratch;}
fn taken(box:Box)->str {try {return box.values.pop();} finally {box.values.clear();}}
fn run(n:int)->int {
 let total=0;let cb:Callable[[int],list[str]]=incoming;
 for i in range(n) {
  let box=Box(["seed","old"]);let old=box.values;
  box.values.extend(cb(i));box.values.append(box.values[0]);box.values.extend(box.values);
  box.values[1:3]=box.values[::-1];box.values[::-1]=box.values;box.values.reverse();box.values.sort();
  box.values[0]="新😀"+str(i);del box.values[::3];box.values+=["tail"];let popped=taken(box);
  try {box.values.extend(failed());} except ValueError {total+=len(box.values);}
  try {box.values.extend(["partial",str(int("bad"))]);} except ValueError {total+=len(box.values);}
  for value in old {total+=len(value);}total+=len(popped);
 }
 return total;
}''',module=True)
        ExceptionResourceTests().check_resources(cell_reference(native),sizes=(1,2,101,1001),native_source=native)


class StringFieldMutationTypeTests(unittest.TestCase):
    setUp=checks.SourceCheckTests.setUp
    source=checks.SourceCheckTests.source
    check=checks.SourceCheckTests.check

    def test_mutation_type_errors_and_unsupported_sort_options_remain_explicit(self):
        prefix='struct Box {values:list[str];} fn main()->int {let box=Box(["a"]);'
        for body in ('box.values.append(7);','box.values.extend([7]);','box.values[0]=7;','box.values[1:2]=[7];','box.values.pop(1.5);'):
            with self.subTest(body=body):
                status,report=self.check(self.source(prefix+body+'return 0;}'))
                self.assertEqual(status,1,report)
        status,report=self.check(self.source(prefix+'box.values.pop(unknown);return 0;}'))
        self.assertEqual(status,1,report)
        self.assertNotIn('type_details',report['diagnostics'][0])
        status,report=self.check(self.source(prefix+'box.values.append("b");box.values.sort();return 0;}'))
        self.assertEqual(status,0,report)


if __name__=='__main__':unittest.main()