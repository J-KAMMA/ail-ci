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

PROVIDER = "class FaultBox:\n\n    def __init__(self, fault: exception, faults: list[exception]):\n        self.fault = fault\n        self.faults = faults\n\nclass NestedFault:\n\n    def __init__(self, box: FaultBox):\n        self.box = box\n\ndef make(text: str) -> exception:\n    return ValueError(text)\n\ndef boxed(fault: exception, faults: list[exception]) -> FaultBox:\n    return FaultBox(fault, faults)\n\ndef nested(box: FaultBox) -> NestedFault:\n    return NestedFault(box)\n\ndef keep(value: exception) -> exception:\n    return value\n\ndef listed(values: list[exception]) -> list[exception]:\n    return values\n\ndef caught(text: str) -> FaultBox:\n    try:\n        raise make(text)\n    except ValueError as e:\n        return boxed(e, [e])\n    finally:\n        print('finally', text)\n    return boxed(RuntimeError(), [])\n"
RELAY = 'def replace(box: FaultBox, value: exception) -> None:\n    box.fault = value\n\ndef replace_list(box: FaultBox, values: list[exception]) -> None:\n    box.faults = values\n\ndef message(owner: NestedFault) -> str:\n    return owner.box.fault.message\n\ndef tail(values: list[exception]) -> exception:\n    return values.pop()\n'
ENTRY = "def side(values: list[exception], text: str) -> exception:\n    value = make(text)\n    values.append(value)\n    print('side', text)\n    return value\n\ndef run(n: int) -> None:\n    values: list[exception] = []\n    box = boxed(side(values, 'first'), listed(values))\n    owner = nested(box)\n    alias = box\n    held = box.fault\n    copied = message(owner)\n    box.fault = box.fault\n    box.faults = box.faults\n    replace(alias, make('replacement'))\n    replace_list(box, [])\n    print(copied, held.kind, held.message, message(owner), len(values), len(box.faults))\n    for i in range(n):\n        values.append(make('日本😀' + str(i)))\n    if n > 0:\n        print(values[-1].message)\n    popped = tail(values)\n    values.clear()\n    print(popped.message, len(values))\n    values.append(popped)\n    values[0] = values[0]\n    values[-1] = held\n    print(values[0].message)\n    returned = caught('escaped' + str(n))\n    escaped = returned.faults[0]\n    text = escaped.message\n    returned.fault = make('new')\n    returned.faults.clear()\n    returned = boxed(make('gone'), [])\n    for i in range(257):\n        churn = caught('churn' + str(i))\n    print(text, escaped.kind, escaped.message, copied)\n"
CLIENT='import sys\n\ndef main() -> int:\n    run(int(sys.argv[1]))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


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
            _,exports,_=module.typed_module(PROVIDER+RELAY,
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
        source='import sys\n\ndef main() -> int:\n    values: list[exception] = []\n    try:\n        values.pop()\n    except IndexError:\n        print(\'empty pop\')\n    try:\n        print(values[0].message)\n    except IndexError:\n        print(\'empty get\')\n    try:\n        values[0] = make(\'bad\')\n    except IndexError:\n        print(\'empty store\')\n    values.append(make(\'held\'))\n    for index in [-2, 1, 9223372036854775807]:\n        try:\n            print(values[index].message)\n        except IndexError:\n            print(\'get bounds\')\n        try:\n            values[index] = make(\'bad\')\n        except IndexError:\n            print(\'store bounds\')\n    print(values[-1].message)\n    values.clear()\n    values.clear()\n    print(len(values))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'
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