"""Deep owned dictionary fields and invalid mutations."""
import ast
import re
import subprocess
import unittest
from ail_syntax import translate
import test_ail_c_objects as support


def build(case,name,source,modules=()):
    paths=[]; seen=set()
    def include(module):
        if module in seen:return
        seen.add(module)
        text=(support.ROOT/'language_examples'/(module+'.ail')).read_text(encoding='utf8')
        for dependency in re.findall(r'^use (\w+);',text,re.M):include(dependency)
        paths.append(case.write(module+'.ail',text))
    for module in modules:include(module)
    ast.parse(translate(source,imports=[]))
    path=case.write(name+'.ail',source);output=case.root/name
    result=case.command('compile',path,*(arg for p in paths for arg in ('--module',p)),'-o',output)
    case.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
    return output if output.exists() else output.with_suffix('.exe')


SOURCE=r'''struct Maps { counts: dict[str,int]; texts: dict[str,str]; blobs: dict[str,bytes]; }
fn relay(box: Maps) -> dict[str,int] { return box.counts; }
fn receiver(box: Maps) -> Maps { print("receiver"); return box; }
fn rhs() -> dict[str,int] { print("rhs"); return {"once":7}; }
fn fail() -> dict[str,int] { raise ValueError; let empty:dict[str,int]={}; return empty; }
fn main() -> int {
 let counts: dict[str,int] = {}; let texts: dict[str,str] = {}; let blobs: dict[str,bytes] = {};
 let n=int(sys.argv[1]); for i in range(n) { let key=str(i)+"\0😀"; counts[key]=i; texts[key]=key; blobs[key]=key.encode(); }
 let box=Maps(counts,texts,blobs); counts.clear(); texts.clear(); blobs.clear();
 let c=box.counts; let t=box.texts; let b=box.blobs;
 box.counts=box.counts; box.texts={}; box.blobs={};
 for i in range(257) { let churn=Maps({}, {"廃棄":"😀"+str(i)}, {"廃棄":bytes(8193)}); }
 let output: list[str] = [];
 for key,value in c.items() { output.append(key.encode().hex()+":"+str(value)+":"+t[key].encode().hex()+":"+b[key].hex()); }
 print("\n".join(output)); c.clear(); if len(box.counts)!=n { return 8; }
 try { box.counts={"bad":10//0}; } except ZeroDivisionError { let caught:int=1; }
 if len(box.counts)!=n { return 9; }
 let returned=relay(box); if len(returned)!=n { return 10; }
 let keys=box.counts.keys(); let values=box.counts.values(); let copy=box.counts.copy();
 if len(keys)!=n or len(values)!=n or len(copy)!=n { return 11; }
 if False { box.counts=fail(); }
 let alias=box; receiver(box).counts=rhs();
 if alias.counts.get("once",0)!=7 or alias.counts["once"]!=7 { return 12; }
 box=Maps({}, {}, {}); if len(returned)!=n { return 13; }
 box.counts={"first":1,"second":2}; let seen:list[str]=[];
 for key,value in box.counts.items() { seen.append(key+str(value)); box.counts={"changed":9}; }
 if "|".join(seen)!="first1|second2" { return 14; }
 box.counts={"first":1,"second":2}; seen=[];
 for key in box.counts { seen.append(key); box.counts={"changed":9}; }
 if "|".join(seen)!="first|second" { return 15; } return 0;
}'''


class MapFieldTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def test_owned_snapshot_selfreplacement_failed_rhs_and_retention(self):
        executable=build(self,'map_fields',SOURCE)
        for n in (0,1,16,8191,8192,8193):
            rows=[]
            for i in range(n):
                key=str(i)+'\0😀'; h=key.encode().hex();rows.append(f'{h}:{i}:{h}:{h}')
            expected=('\n'.join(rows)+'\nrhs\nreceiver\n').encode()
            result=subprocess.run([str(executable),str(n)],capture_output=True,timeout=120)
            self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,expected,b''))

    def test_invalid_mutations_and_wrong_field_types_refused_after_parse(self):
        for i,statement in enumerate(('box.counts[1]=1;','del box.counts[1];','box.counts.clear(1);',
                                     'box.counts.pop("x","bad");','box.counts.update({"x":"bad"});','box.counts.setdefault("x","bad");',
                                     'box.texts["x"]=1;','box.blobs["x"]="y";','box.counts={"x":"bad"};')):
            program='struct Maps { counts: dict[str,int]; texts: dict[str,str]; blobs: dict[str,bytes]; } fn main() -> int { let box=Maps({"x":1},{"x":"v"},{"x":b"v"}); '+statement+' return 0; }'
            ast.parse(translate(program,imports=[]));path=self.write('bad'+str(i)+'.ail',program);output=self.root/('bad'+str(i))
            result=self.command('compile',path,'-o',output);self.assertNotEqual(result.returncode,0,statement)
            self.assertNotIn(b'Traceback',result.stderr);self.assertFalse(output.exists());self.assertFalse(output.with_suffix('.exe').exists())


if __name__=='__main__':unittest.main()
