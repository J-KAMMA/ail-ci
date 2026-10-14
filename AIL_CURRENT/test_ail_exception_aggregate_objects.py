"""Exception aggregate ownership through relocated, source-free object providers."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_c_objects as support

PROVIDER = '''struct FaultBox { fault:exception; faults:list[exception]; }
struct NestedFault { box:FaultBox; }
fn make(text:str)->exception { return ValueError(text); }
fn boxed(fault:exception,faults:list[exception])->FaultBox { return FaultBox(fault,faults); }
fn nested(box:FaultBox)->NestedFault { return NestedFault(box); }
fn keep(value:exception)->exception { return value; }
fn listed(values:list[exception])->list[exception] { return values; }
fn caught(text:str)->FaultBox {
 try { raise make(text); } except ValueError as e { return boxed(e,[e]); }
 finally { print("finally",text); }
 return boxed(RuntimeError(),[]);
}
'''
RELAY = '''fn replace(box:FaultBox,value:exception)->void { box.fault=value; }
fn replace_list(box:FaultBox,values:list[exception])->void { box.faults=values; }
fn message(owner:NestedFault)->str { return owner.box.fault.message; }
fn tail(values:list[exception])->exception { return values.pop(); }
'''
ENTRY = '''fn side(values:list[exception],text:str)->exception {
 let value=make(text); values.append(value); print("side",text); return value;
}
fn run(n:int)->void {
 let values:list[exception]=[];
 let box=boxed(side(values,"first"),listed(values));
 let owner=nested(box); let alias=box; let held=box.fault;
 let copied=message(owner); box.fault=box.fault; box.faults=box.faults;
 replace(alias,make("replacement")); replace_list(box,[]);
 print(copied,held.kind,held.message,message(owner),len(values),len(box.faults));
 for i in range(n) { values.append(make("日本😀"+str(i))); }
 if n>0 { print(values[-1].message); }
 let popped=tail(values); values.clear(); print(popped.message,len(values));
 values.append(popped); values[0]=values[0]; values[-1]=held;
 print(values[0].message);
 let returned=caught("escaped"+str(n)); let escaped=returned.faults[0];
 let text=escaped.message; returned.fault=make("new"); returned.faults.clear();
 returned=boxed(make("gone"),[]);
 for i in range(257) { let churn=caught("churn"+str(i)); }
 print(text,escaped.kind,escaped.message,copied);
}
'''
CLIENT='fn main()->int { run(int(sys.argv[1])); return 0; }'


def expected(n):
    # Deliberately independent Python whole-output oracle: no AIL translation.
    values=[ValueError('first')]
    held=values[0]
    copied=str(held)
    lines=['side first',f'{copied} ValueError {held} replacement 1 0']
    values.extend(ValueError('日本😀'+str(i)) for i in range(n))
    if n:
        lines.append(str(values[-1]))
    popped=values.pop()
    values.clear()
    lines.extend((f'{popped} 0','first',f'finally escaped{n}'))
    lines.extend('finally churn'+str(i) for i in range(257))
    lines.append(f'escaped{n} ValueError escaped{n} first')
    return ('\n'.join(lines)+'\n').encode()


class ExceptionAggregateObjectTests(unittest.TestCase):
    def setUp(self):
        if self._testMethodName != 'test_pure_schema_roundtrip_and_signature_kinds':
            support.CObjectTests.setUp(self)
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def test_pure_schema_roundtrip_and_signature_kinds(self):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            import module_object as module
            specs={}
            _,exports,_=module.typed_module(translate(PROVIDER+RELAY,module=True,imports=[]),
                                           integer_lists=True,structs=specs)
            self.assertEqual(module.ABI_VERSION,11)
            self.assertEqual(specs['FaultBox']['fields'],[['fault','exception'],['faults','handle_list:exception']])
            self.assertEqual(exports['listed']['params'],[['values','handle_list:exception']])
            self.assertEqual(exports['listed']['result'],'handle_list:exception')
            self.assertEqual(module.native_kind('handle_list:exception'),('hlist','exception'))
            module._validate_struct_graph(specs)
            ast.parse(module._struct_source(specs))
            for bad in ('handle_list:Exception','handle_list:exception:extra','handle_list:str'):
                with self.assertRaises(ValueError):
                    module._valid_struct('Bad',{'fields':[['value',bad]]})
        finally:
            sys.path.pop(0)

    def test_relocated_source_free_nested_fields_aliases_and_whole_output(self):
        provider=self.ail_build('provider',PROVIDER,library=True)
        relay=self.ail_build('relay',RELAY,provider,library=True)
        entry=self.ail_build('entry',ENTRY,provider,relay,library=True)
        folder=self.root/'移動 exceptions 😀'; folder.mkdir()
        objects=[]
        for obj in (provider,relay,entry):
            moved=folder/obj.name; obj.rename(moved)
            Path(str(obj)+'.json').rename(Path(str(moved)+'.json')); objects.append(moved)
        self.assertFalse(list(self.root.rglob('*.ail')))
        contract=json.loads(Path(str(objects[0])+'.json').read_bytes())['contract']
        self.assertEqual(contract['version'],11)
        self.assertEqual(contract['structs']['FaultBox']['fields'],
                         [['fault','exception'],['faults','handle_list:exception']])
        before=self.snapshot(*objects)
        for index,order in enumerate((objects,list(reversed(objects)))):
            executable=self.ail_build('client'+str(index),CLIENT,*order)
            for n in (0,1,17,4097):
                with self.subTest(order=index,n=n):
                    result=subprocess.run([str(executable),str(n)],capture_output=True,timeout=120)
                    actual=result.stdout.replace(b'\r\n',b'\n'); reference=expected(n)
                    self.assertEqual((result.returncode,result.stderr),(0,b''))
                    self.assertTrue(actual==reference,
                        f'output SHA256 {hashlib.sha256(actual).hexdigest()}/{hashlib.sha256(reference).hexdigest()}')
            self.assertEqual(self.snapshot(*objects),before)
        metadata_path=Path(str(objects[0])+'.json'); original=metadata_path.read_bytes()
        try:
            metadata=json.loads(original)
            metadata['contract']['identity']['implementation']['module_object.py']='0'*64
            metadata_path.write_text(json.dumps(metadata),encoding='utf8')
            source=self.write('old.ail',CLIENT)
            result=self.command('compile',source,*[arg for obj in objects for arg in ('--object',obj)],
                                '-o',self.root/'old')
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'identity mismatch',result.stderr)
            self.assertFalse((self.root/'old').exists())
            self.assertFalse((self.root/'old.exe').exists())
        finally:
            metadata_path.write_bytes(original)
        self.assertEqual(self.snapshot(*objects)[0][0],before[0][0])

    def test_object_list_empty_index_width_and_type_boundaries(self):
        provider=self.ail_build('bounds_provider',PROVIDER,library=True)
        source='''fn main()->int {
 let values:list[exception]=[];
 try { values.pop(); } except IndexError { print("empty pop"); }
 try { print(values[0].message); } except IndexError { print("empty get"); }
 try { values[0]=make("bad"); } except IndexError { print("empty store"); }
 values.append(make("held"));
 for index in [-2,1,9223372036854775807] {
  try { print(values[index].message); } except IndexError { print("get bounds"); }
  try { values[index]=make("bad"); } except IndexError { print("store bounds"); }
 }
 print(values[-1].message); values.clear(); values.clear(); print(len(values));
 return 0;
}'''
        exe=self.ail_build('bounds',source,provider)
        result=subprocess.run([str(exe)],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stderr),(0,b''))
        self.assertEqual(result.stdout.replace(b'\r\n',b'\n'),
                         b'empty pop\nempty get\nempty store\n'+
                         b'get bounds\nstore bounds\n'*3+b'held\n0\n')
        for index,statement in enumerate(('let box=FaultBox(1,[]);',
                                          'let box=FaultBox(make("x"),[1]);',
                                          'let values:list[exception]=[make("x")]; values.append(1);',
                                          'let values:list[exception]=[make("x")]; values[0]=1;')):
            path=self.write('bad'+str(index)+'.ail','fn main()->int { '+statement+' return 0; }')
            result=self.command('compile',path,'--object',provider,'-o',self.root/('bad'+str(index)))
            self.assertNotEqual(result.returncode,0)


if __name__=='__main__': unittest.main()