"""Independent JSON/dict/filesystem reference for the persistent AIL CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_ail_c_objects as support

EXAMPLES=support.ROOT/'language_examples'


def object_text(text):
    def pairs(items):
        values={}
        for key,value in items:
            if key in values:raise ValueError('duplicate key')
            values[key]=value
        return values
    value=json.loads(text,object_pairs_hook=pairs)
    if not isinstance(value,dict) or any(not isinstance(v,str) for v in value.values()):raise ValueError('string object required')
    for key,v in value.items():key.encode('utf8');v.encode('utf8')
    return value


def reference(state,data):
    values=object_text(state) if state is not None else {}
    replies=[]
    for line in data.decode('utf8').split('\n'):
        if line in ('','\r'):continue
        command=object_text(line);op=command.get('op')
        if op=='count' and set(command)=={'op'}:reply={'ok':True,'count':len(values)}
        elif op=='set' and set(command)=={'op','key','value'}:
            values[command['key']]=command['value'];reply={'ok':True}
        elif op in ('get','delete') and set(command)=={'op','key'}:
            key=command['key'];found=key in values;reply={'ok':True,'found':found}
            if found and op=='get':reply['value']=values[key]
            if found and op=='delete':del values[key]
        else:raise ValueError('invalid operation')
        replies.append(reply)
    dump=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':'))
    report=(''.join(dump(item)+'\n' for item in replies)).encode()
    snapshot=(dump(dict(sorted(values.items())))+'\n').encode()
    return report,snapshot


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('gcc'),'C compiler required')
class JsonKvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix='ail-json-kv-');cls.addClassCleanup(temporary.cleanup)
        cls.root=Path(temporary.name);obj=cls.root/'identity.o';exe=cls.root/'json-kv'
        for command in (('compile-c',EXAMPLES/'file_identity.c','--interface',EXAMPLES/'file_identity.json','-o',obj),('compile',EXAMPLES/'json_kv_main.ail','--object',obj,'-o',exe)):
            result=subprocess.run([sys.executable,'-X','utf8','-B',support.ROOT/'ail_chatgpt.py',*map(str,command)],capture_output=True,timeout=180)
            if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        cls.exe=exe if exe.is_file() else exe.with_suffix('.exe')

    def invoke(self,data,state=None,name='case'):
        folder=self.root/name;folder.mkdir();source=folder/'input.jsonl';db=folder/'state.json'
        source.write_bytes(data)
        if state is not None:db.write_bytes(state.encode())
        result=subprocess.run([self.exe,source,db],capture_output=True,timeout=60)
        return result,source,db

    def test_full_reference_unicode_operations_and_persistence(self):
        commands=[{'op':'set','key':'','value':'empty key'},{'op':'set','key':'日本😀\0','value':'x\n\r\t"\\\0\u2028y'}, {'op':'get','key':'日本😀\0'},{'op':'get','key':'missing'},{'op':'count'},{'op':'delete','key':''},{'op':'delete','key':'missing'},{'op':'count'}]
        data=('\r\n'+'\r\n'.join(json.dumps(c,ensure_ascii=False) for c in commands)).encode()
        expected=reference('{"old":"kept"}',data);result,source,db=self.invoke(data,'{"old":"kept"}','unicode')
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected[0],b''));self.assertEqual(db.read_bytes(),expected[1]);self.assertEqual(source.read_bytes(),data)
        second=b'{"op":"get","key":"old"}\n{"op":"count"}'
        source.write_bytes(second);expected=reference(db.read_text(encoding='utf8'),second)
        result=subprocess.run([self.exe,source,db],capture_output=True,timeout=30)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected[0],b''));self.assertEqual(db.read_bytes(),expected[1]);self.assertFalse(Path(str(db)+'.ail-stage').exists())

    def test_invalid_late_request_and_state_preserve_files(self):
        bad=[b'{"op":"set","key":"x","value":"y"}\n{',b'{"op":"get"}',b'{"op":"set","key":"x","value":1}',b'{"op":"count","op":"count"}',b'{"op":"unknown","key":"x"}',b'{"op":"get","key":"x","extra":"x"}',b'\xff',b'{"op":"set","key":"x","value":"\\ud800"}',b'[]',b'   ']
        for index,data in enumerate(bad):
            with self.subTest(index=index):
                result,source,db=self.invoke(data,'{"original":"unchanged"}',f'bad{index}')
                self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,b'');self.assertEqual(db.read_bytes(),b'{"original":"unchanged"}');self.assertEqual(source.read_bytes(),data);self.assertFalse(Path(str(db)+'.ail-stage').exists())
        for index,state in enumerate(('{"x":1}','{"x":"a","x":"b"}','[]')):
            result,source,db=self.invoke(b'{"op":"count"}',state,f'state{index}')
            self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertEqual(db.read_bytes(),state.encode())

    def test_command_frame_file_item_and_report_limits(self):
        count=b'{"op":"count"}'
        for n in (4096,4097):
            data=b'\n'.join([count]*n);result,source,db=self.invoke(data,'{}',f'commands{n}')
            self.assertEqual(result.returncode,0 if n==4096 else 2)
            if n==4096:self.assertEqual((result.stdout,db.read_bytes()),reference('{}',data))
            else:self.assertEqual((result.stdout,db.read_bytes()),(b'',b'{}'))
        for n in (8192,8193):
            result,source,db=self.invoke(b'\n'*n,'{}',f'frames{n}')
            self.assertEqual((result.returncode,result.stdout,db.read_bytes()),(0,b'',b'{}\n') if n==8192 else (2,b'',b'{}'))
        line=b' '*(1048576-len(count))+count
        result,source,db=self.invoke((line[1:]+b'\n')*7+line,'{}','file-exact')
        self.assertEqual((result.returncode,result.stdout,db.read_bytes()),(0,b'{"ok":true,"count":0}\n'*8,b'{}\n'))
        for name,data in (('file-over',b'\n'*8388609),('line-over',line+b' ')):
            result,source,db=self.invoke(data,'{}',name);self.assertEqual((result.returncode,result.stdout,db.read_bytes()),(2,b'',b'{}'))
        state=json.dumps({str(i):'v' for i in range(4096)},separators=(',',':'))
        for name,key,accepted in (('items-replace','0',True),('items-add','new',False)):
            data=json.dumps({'op':'set','key':key,'value':'updated'}).encode();result,source,db=self.invoke(data,state,name)
            self.assertEqual(result.returncode,0 if accepted else 2)
            if accepted:self.assertEqual((result.stdout,db.read_bytes()),reference(state,data))
            else:self.assertEqual((result.stdout,db.read_bytes()),(b'',state.encode()))
        value='v'*65536;state=json.dumps({'k':value},separators=(',',':'))
        get=b'{"op":"get","key":"k"}';one=json.dumps({'ok':True,'found':True,'value':value},separators=(',',':')).encode()+b'\n'
        maximum=16777216//len(one)
        for n in (maximum,maximum+1):
            data=b'\n'.join([get]*n);result,source,db=self.invoke(data,state,f'report{n}')
            self.assertEqual(result.returncode,0 if n==maximum else 2)
            if n==maximum:self.assertEqual((result.stdout,db.read_bytes()),reference(state,data))
            else:self.assertEqual((result.stdout,db.read_bytes()),(b'',state.encode()))
    def test_bounds_aliases_and_preexisting_stage(self):
        for index,(key,value,accepted) in enumerate((('x'*1024,'v',True),('x'*1025,'v',False),('😀'*256,'v',True),('😀'*257,'v',False),('k','v'*65536,True),('k','v'*65537,False))):
            data=json.dumps({'op':'set','key':key,'value':value},ensure_ascii=False).encode();result,source,db=self.invoke(data,'{}',f'limit{index}')
            self.assertEqual(result.returncode,0 if accepted else 2)
            if accepted:self.assertEqual((result.stdout,db.read_bytes()),reference('{}',data))
            else:self.assertEqual((result.stdout,db.read_bytes()),(b'',b'{}'))
        folder=self.root/'alias';folder.mkdir();source=folder/'data';source.write_bytes(b'{"op":"count"}')
        for path in (source,folder/'hardlink'):
            if path!=source:os.link(source,path)
            result=subprocess.run([self.exe,source,path],capture_output=True,timeout=30);self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertEqual(source.read_bytes(),b'{"op":"count"}')
        db=folder/'state.json';db.write_bytes(b'{}');stage=Path(str(db)+'.ail-stage');stage.mkdir();(stage/'kept').write_bytes(b'owned by someone else')
        result=subprocess.run([self.exe,source,db],capture_output=True,timeout=30);self.assertEqual((result.returncode,result.stdout),(2,b''));self.assertEqual(db.read_bytes(),b'{}');self.assertEqual((stage/'kept').read_bytes(),b'owned by someone else')

if __name__=='__main__':unittest.main()