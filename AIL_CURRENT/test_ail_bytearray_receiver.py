"""Receiver-store removal gates: pure names and preserved effectful captures."""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_callable_values as callbacks
import test_ail_c_objects as support
from test_ail_map_fields import build
from test_ail_exception_resources import ALLOCATOR, ROOT


HEADER=r'''struct Holder { buffer:bytearray; trace:str; }
fn emit(buffer:bytearray)->void { let data=bytes(buffer); write_stdout_bytes((str(len(data))+":").encode()); write_stdout_bytes(data); }
fn mutate(buffer:bytearray)->int {
 let value:int=255; let extra:bytes=b"\0\xff";
 buffer.append(value); buffer.extend(extra); buffer.extend(buffer); buffer.reverse(); let popped=buffer.pop(); return popped;
}
'''
SOURCE=HEADER+r'''fn run(n:int)->int {
 let input:list[int]=[i%256 for i in range(n)]; let buffer=bytearray(input); let alias=buffer;
 let copied=buffer.copy(); let frozen=bytes(buffer); let result=mutate(buffer);
 write_stdout_bytes((str(result)+":").encode()); emit(buffer); emit(alias); emit(copied);
 let amount:int=0; buffer.append(amount); buffer.extend(b"literal"); let sliced=buffer[1:]; buffer.clear();
 emit(buffer); emit(sliced); write_stdout_bytes((str(len(frozen))+":").encode()); write_stdout_bytes(frozen); return 0;
}'''
EFFECTS=HEADER+r'''fn replace(owner:Holder)->int { owner.trace+="A"; owner.buffer=bytearray(b"new"); return 37; }
fn receiver(owner:Holder)->Holder { owner.trace+="O"; return owner; }
fn extend_rhs(owner:Holder)->bytes { owner.trace+="E"; owner.buffer=bytearray(b"new"); return b"extra"; }
fn index(owner:Holder)->int { owner.trace+="I"; owner.buffer=bytearray(b"new"); return 0; }
fn failed(owner:Holder)->int { owner.trace+="F"; owner.buffer.append(99); raise ValueError; return 0; }
fn run(n:int)->int {
 let owner=Holder(bytearray(b"old"),""); let x=owner.buffer;
 x.append(replace(owner)); write_stdout_bytes(owner.trace.encode()); emit(x); emit(owner.buffer);
 owner=Holder(bytearray(b"old"),""); let retained=owner.buffer;
 receiver(owner).buffer.extend(extend_rhs(owner)); write_stdout_bytes(owner.trace.encode()); emit(retained); emit(owner.buffer);
 owner=Holder(bytearray(b"old"),""); let popped=receiver(owner).buffer.pop(index(owner));
 write_stdout_bytes((owner.trace+str(popped)).encode()); emit(owner.buffer);
 owner=Holder(bytearray(b"old"),""); let alias=owner.buffer;
 try { alias.append(failed(owner)); } except ValueError { write_stdout_bytes(owner.trace.encode()); }
 emit(alias); emit(owner.buffer); return 0;
}'''
BOUNDS=HEADER+r'''fn run(n:int)->int {
 let buffer=bytearray(); let caught:int=0; buffer.append(0); buffer.append(255);
 try { buffer.append(-1); } except ValueError { caught+=1; }
 try { buffer.append(256); } except ValueError { caught+=1; }
 try { buffer.pop(9223372036854775807); } except IndexError { caught+=1; }
 try { buffer.pop(-9223372036854775808); } except IndexError { caught+=1; }
 let maybe=bytearray(); if n>0 { let bound=bytearray(b"bound"); bound.append(17); maybe=bound; }
 if False { let unchosen=bytearray(); unchosen.append(-1); }
 emit(buffer); emit(maybe); write_stdout_bytes((str(caught)+":").encode()); buffer.clear();
 try { buffer.pop(); } except IndexError { caught+=1; }
 write_stdout_bytes(str(caught).encode()); return 0;
}'''
RESOURCE=HEADER+r'''fn step(i:int)->int {
 let values:list[int]=[j%256 for j in range(33)]; let buffer=bytearray(values); let alias=buffer;
 let copied=buffer.copy(); let frozen=bytes(buffer); let old=mutate(alias); let owner=Holder(buffer,"");
 try { buffer.append(failed(owner)); } except ValueError { let caught:int=1; }
 let size=len(buffer)+len(copied)+len(frozen)+old; buffer.clear(); owner.buffer=bytearray(); return size;
}
fn failed(owner:Holder)->int { owner.buffer.append(17); raise ValueError; return 0; }
fn run(n:int)->int { let total:int=0; for i in range(n) { total+=step(i); } return total; }
'''


def oracle(source,n):
    raw=bytearray();namespace={'write_stdout_bytes':raw.extend}
    exec(callbacks.oracle_source(translate(source,module=True,imports=[])),namespace)
    return namespace['run'](n),bytes(raw)


class BytearrayReceiverTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def compare(self,exe,source,n):
        value,expected=oracle(source,n);result=subprocess.run([str(exe),str(n)],capture_output=True,timeout=120)
        self.assertEqual(result.returncode,value,result.stderr[:2000].decode(errors='replace'));self.assertFalse(result.stderr,result.stderr[:2000])
        if result.stdout!=expected:
            offset=next((i for i,(a,b) in enumerate(zip(result.stdout,expected)) if a!=b),min(len(result.stdout),len(expected)));start=max(0,offset-16)
            self.fail(f'bytes actual={len(result.stdout)} sha={hashlib.sha256(result.stdout).hexdigest()}, expected={len(expected)} sha={hashlib.sha256(expected).hexdigest()}, '
                      f'first={offset}, actual={result.stdout[start:offset+17]!r}, expected={expected[start:offset+17]!r}')

    def test_named_local_and_param_alias_pure_mutations_self_extend_snapshots(self):
        exe=build(self,'names',SOURCE+'fn main()->int { return run(int(sys.argv[1])); }')
        for n in (0,1,7,8,9,31,32,33):self.compare(exe,SOURCE,n)

    def test_effectful_name_attribute_and_index_arguments_hold_selected_receiver(self):
        exe=build(self,'effects',EFFECTS+'fn main()->int { return run(0); }');self.compare(exe,EFFECTS,0)

    def test_value_width_index_bounds_conditional_binding_and_unchosen_path(self):
        exe=build(self,'bounds',BOUNDS+'fn main()->int { return run(int(sys.argv[1])); }')
        for n in (0,1):self.compare(exe,BOUNDS,n)

    def test_short_exception_alias_loop_cleanup_live_zero_and_bounded_peak(self):
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            code=to_c(translate(RESOURCE,module=True,imports=[]),name='run',strict=True)
        finally:sys.path.pop(0)
        drain='for(int64_t i=0;i<ail__blk_cache_n;i++)count_free(ail__blk_cache[i].p);ail__blk_cache_n=0;' if 'ail__blk_cache_n' in code else ''
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in code else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in code else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host=r'''int main(int argc,char **argv){int64_t result=run(strtoll(argv[1],NULL,10));DRAIN
 fprintf(stderr,"{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"frames\":%d,\"handled\":%d}\n",(long long)result,live,live_bytes,peak_bytes,ail_cleanup_top!=NULL,ail_handled_code);return 0;}'''
        path=self.write('resource.c',ALLOCATOR+code+host.replace('DRAIN',drain));exe=self.root/('resource.exe' if os.name=='nt' else 'resource')
        cc=os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc');result=subprocess.run([cc,'-std=c11','-O2',str(path),'-lm','-o',str(exe)],capture_output=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'));peaks=[]
        for n in (3,31):
            expected,raw=oracle(RESOURCE,n);self.assertEqual(raw,b'');result=subprocess.run([str(exe),str(n)],capture_output=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[:2000]);self.assertEqual(result.stdout,b'');metrics=json.loads(result.stderr)
            self.assertEqual((metrics['result'],metrics['live'],metrics['bytes'],metrics['frames'],metrics['handled']),(expected,0,0,0,0));peaks.append(metrics['peak'])
        self.assertLessEqual(peaks[1],peaks[0]*2+65536)


if __name__=='__main__':unittest.main()
