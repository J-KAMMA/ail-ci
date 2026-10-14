"""AIL localhost servers with independent Python clients and bounded lifetimes."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import threading
import unittest

from ail_syntax import translate
import test_ail_c_objects as support
from test_ail_map_fields import build
from test_ail_exception_resources import ALLOCATOR, ROOT


PROVIDER=r'''fn echo_peer(peer:tcpsocket)->int {
 let total:int=0; let buffer=bytearray(8193);
 while True { let count=peer.recv_into(buffer); if count==0 { break; } peer.send(buffer[:count]); total+=count; }
 peer.shutdown_write(); return total;
}'''
SERVER=PROVIDER+r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,4); print(listener.local_port()); flush_stdout();
 let peer=listener.accept(); listener.close(); let total=echo_peer(peer); peer.close(); print(total); return 0;
}'''
SHARED=PROVIDER+r'''struct Holder { listener:tcpsocket; }
fn identity(peer:tcpsocket)->tcpsocket { return peer; }
fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,4); let holder=Holder(listener); let callback:Callable[[tcpsocket],tcpsocket]=identity;
 let alias=callback(holder.listener); print(listener.local_port()); flush_stdout();
 let first=alias.accept(); let kept=identity(first); let second=listener.accept(); second.close(); alias.close();
 if listener.closed!=1 or kept.closed!=0 { return 9; }
 let total=echo_peer(kept); first.close(); kept.close(); print(total); return 0;
}'''
ROLES=r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,4); let port=listener.local_port(); print(port); flush_stdout(); let caught:int=0;
 try { listener.send(b""); } except OSError { caught+=1; }
 try { listener.recv(0); } except OSError { caught+=1; }
 try { listener.recv_into(bytearray()); } except OSError { caught+=1; }
 try { listener.shutdown_write(); } except OSError { caught+=1; }
 let peer=listener.accept(); try { peer.accept(); } except OSError { caught+=1; }
 if peer.local_port()!=port { return 9; } peer.close(); listener.close(); listener.close();
 try { listener.accept(); } except ValueError { caught+=1; }
 try { listener.local_port(); } except ValueError { caught+=1; }
 try { listener.send(b""); } except ValueError { caught+=1; }
 try { listener.recv(0); } except ValueError { caught+=1; }
 try { listener.shutdown_write(); } except ValueError { caught+=1; }
 print(caught); return 0;
}'''
INVALID=r'''fn main()->int {
 let caught:int=0;
 try { tcp_listen("",0,1); } except ValueError { caught+=1; }
 try { tcp_listen("127\0.0.0.1",0,1); } except ValueError { caught+=1; }
 try { tcp_listen("127.0.0.1é",0,1); } except ValueError { caught+=1; }
 try { tcp_listen("127.0.0.1",-1,1); } except ValueError { caught+=1; }
 try { tcp_listen("127.0.0.1",65536,1); } except ValueError { caught+=1; }
 try { tcp_listen("127.0.0.1",0,0); } except ValueError { caught+=1; }
 try { tcp_listen("127.0.0.1",0,2147483648); } except ValueError { caught+=1; }
 print(caught); return 0;
}'''
NAMES=r'''fn accept()->int { return 17; } fn bind()->int { return 19; } fn listen()->int { return 23; }
fn main()->int { let listener=tcp_listen("127.0.0.1",0,1); listener.close(); print(accept()); print(bind()); print(listen()); return 0; }'''
RESOURCE=PROVIDER+r'''fn run(n:int)->int {
 let listener=tcp_listen("127.0.0.1",0,4); print(listener.local_port()); flush_stdout(); let total:int=0;
 try {
  for i in range(n) {
   let peer=listener.accept();
   try { total+=echo_peer(peer); let temporary=bytearray(17); raise ValueError; }
   except ValueError { total+=1; } finally { peer.close(); }
  }
 } finally { listener.close(); }
 return total;
}'''


class RunningServer:
    def __init__(self,exe,args=(),cwd=None):self.exe=exe;self.args=args;self.cwd=cwd
    def __enter__(self):
        self.process=subprocess.Popen([str(self.exe),*map(str,self.args)],cwd=self.cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready=queue.Queue()
        self.reader=threading.Thread(target=lambda:ready.put(self.process.stdout.readline()),daemon=True);self.reader.start()
        try:
            line=ready.get(timeout=10);self.port=int(line.strip())
            if not 1<=self.port<=65535:raise ValueError('invalid ephemeral port')
        except Exception:
            self.process.kill();out,err=self.process.communicate(timeout=5);self.reader.join(2)
            raise AssertionError(f'Listener startup failed: stdout={out[:100]!r}, stderr={err[:1000]!r}')
        return self
    def finish(self):
        out,err=self.process.communicate(timeout=15);self.reader.join(2)
        if self.process.returncode:raise AssertionError(f'Server exit {self.process.returncode}: {err[:2000]!r}')
        return out,err
    def __exit__(self,*error):
        if self.process.poll() is None:self.process.kill()
        self.process.communicate(timeout=5);self.reader.join(2)


def client(port,data,host='127.0.0.1'):
    pieces=[]
    with socket.create_connection((host,port),timeout=8) as peer:
        peer.settimeout(8);peer.sendall(data);peer.shutdown(socket.SHUT_WR)
        while True:
            chunk=peer.recv(4096)
            if not chunk:break
            pieces.append(chunk)
    return b''.join(pieces)


class TcpListenerTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def equal(self,actual,expected):
        if actual!=expected:
            offset=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)));start=max(0,offset-16)
            self.fail(f'full bytes actual={len(actual)} sha={hashlib.sha256(actual).hexdigest()}, expected={len(expected)} sha={hashlib.sha256(expected).hexdigest()}, '
                      f'first={offset}, actual={actual[start:offset+17]!r}, expected={expected[start:offset+17]!r}')

    def test_ephemeral_listener_close_keeps_child_echo_full_binary(self):
        exe=build(self,'server',SERVER)
        for n in (0,1,8191,8192,8193):
            data=bytes(i%256 for i in range(n))
            with RunningServer(exe) as server:
                self.equal(client(server.port,data),data);out,err=server.finish()
            self.equal(out.replace(b'\r\n',b'\n'),(str(n)+'\n').encode());self.assertFalse(err,err[:2000])
        with self.subTest(family='IPv6 loopback'):
            try:
                with socket.socket(socket.AF_INET6,socket.SOCK_STREAM) as probe:probe.bind(('::1',0))
            except OSError as error:self.skipTest('IPv6 loopback unavailable: '+str(error))
            ipv6=build(self,'server_ipv6',SERVER.replace('127.0.0.1','::1'));data=bytes(range(256))
            with RunningServer(ipv6) as server:self.equal(client(server.port,data,'::1'),data);out,err=server.finish()
            self.equal(out.replace(b'\r\n',b'\n'),b'256\n');self.assertFalse(err,err[:2000])

    def test_listener_alias_close_and_other_child_do_not_close_kept_peer(self):
        exe=build(self,'shared',SHARED);data=bytes(range(256))+b'\0\xff'
        with RunningServer(exe) as server:
            first=socket.create_connection(('127.0.0.1',server.port),timeout=8)
            try:
                with socket.create_connection(('127.0.0.1',server.port),timeout=8) as second:self.assertEqual(second.recv(1),b'')
                first.sendall(data);first.shutdown(socket.SHUT_WR);pieces=[]
                while True:
                    chunk=first.recv(4096)
                    if not chunk:break
                    pieces.append(chunk)
                self.equal(b''.join(pieces),data)
            finally:first.close()
            out,err=server.finish()
        self.equal(out.replace(b'\r\n',b'\n'),(str(len(data))+'\n').encode());self.assertFalse(err,err[:2000])

    def test_stream_listener_roles_empty_ops_local_port_and_closed_priority(self):
        exe=build(self,'roles',ROLES)
        with RunningServer(exe) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:self.assertEqual(peer.recv(1),b'')
            out,err=server.finish()
        self.equal(out.replace(b'\r\n',b'\n'),b'10\n');self.assertFalse(err,err[:2000])

    def test_invalid_host_port_backlog_types_arity_and_positive_user_names(self):
        invalid=build(self,'invalid',INVALID);result=subprocess.run([str(invalid)],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr[:2000]);self.equal(result.stdout.replace(b'\r\n',b'\n'),b'7\n')
        names=build(self,'names',NAMES);result=subprocess.run([str(names)],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr[:2000]);self.equal(result.stdout.replace(b'\r\n',b'\n'),b'17\n19\n23\n')
        invalid_statements=('tcp_listen(1,0,1);','tcp_listen("127.0.0.1",1.5,1);','tcp_listen("127.0.0.1",0,1.5);','tcp_listen("127.0.0.1",0);',
                           'let listener=tcp_listen("127.0.0.1",0,1); listener.accept(1);','let listener=tcp_listen("127.0.0.1",0,1); listener.local_port(1);')
        for index,statement in enumerate(invalid_statements):
            path=self.write('bad'+str(index)+'.ail','fn main()->int { '+statement+' return 0; }');out=self.root/('bad'+str(index));result=self.command('compile',path,'-o',out)
            self.assertNotEqual(result.returncode,0);self.assertNotIn(b'Traceback',result.stderr);self.assertFalse(out.exists());self.assertFalse(out.with_suffix('.exe').exists())

    def test_source_free_relocated_server_provider(self):
        obj=self.ail_build('provider',PROVIDER,library=True);folder=self.root/'移動😀 listener objects';folder.mkdir();moved=folder/obj.name
        shutil.move(str(obj),moved);shutil.move(str(obj)+'.json',str(moved)+'.json');before=self.snapshot(moved)
        entry=SERVER[len(PROVIDER):];exe=self.ail_build('entry',entry,moved);data=bytes(range(256))*33
        with RunningServer(exe) as server:self.equal(client(server.port,data),data);out,err=server.finish()
        self.equal(out.replace(b'\r\n',b'\n'),(str(len(data))+'\n').encode());self.assertFalse(err,err[:2000]);self.assertEqual(self.snapshot(moved),before)

    def test_short_repeat_throw_finally_heap_frames_and_bounded_peak(self):
        sys.path.insert(0,str(ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            code=to_c(translate(RESOURCE,module=True,imports=[]),name='run',strict=True)
        finally:sys.path.pop(0)
        drain='for(int64_t i=0;i<ail__blk_cache_n;i++)count_free(ail__blk_cache[i].p);ail__blk_cache_n=0;' if 'ail__blk_cache_n' in code else ''
        drain += ('for(int j=0;j<ail__ba_cache_n;j++){count_free(ail__ba_cache[j]->p);count_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
        drain += ('for(int j=0;j<ail__svec_cache_n;j++)count_free(ail__svec_cache_p[j]);ail__svec_cache_n=0;' if 'ail__svec_cache_n' in code else '')  # parked str-list vectors (cruntime ail__svec_cache)
        drain += ('ail__blist_caches_drain();' if 'ail__blist_caches_drain' in code else '')  # parked list[bytes] headers and payload slabs (cruntime ail__blist_cache)
        host=r'''int main(int argc,char **argv) {int64_t result=run(strtoll(argv[1],NULL,10)); DRAIN
 fprintf(stderr,"{\"result\":%lld,\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"frames\":%d,\"handled\":%d}\n",(long long)result,live,live_bytes,peak_bytes,ail_cleanup_top!=NULL,ail_handled_code);return 0;}'''
        path=self.write('resource.c',ALLOCATOR+code+host.replace('DRAIN',drain));exe=self.root/('resource.exe' if os.name=='nt' else 'resource')
        cc=os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc');flags=['-std=c11','-O2',str(path),'-lm','-o',str(exe)]
        if os.name=='nt':flags.append('-lws2_32')
        else:flags.insert(0,'-D_POSIX_C_SOURCE=200809L')
        result=subprocess.run([cc,*flags],capture_output=True,timeout=180);self.assertEqual(result.returncode,0,result.stderr[:2000]);peaks=[]
        for n in (3,17):
            data=bytes(range(256))
            with RunningServer(exe,(n,)) as server:
                for _ in range(n):self.equal(client(server.port,data),data)
                out,err=server.finish()
            self.assertEqual(out,b'');metrics=json.loads(err);self.assertEqual((metrics['result'],metrics['live'],metrics['bytes'],metrics['frames'],metrics['handled']),(257*n,0,0,0,0));peaks.append(metrics['peak'])
        self.assertLessEqual(peaks[1],peaks[0]*2+65536)


if __name__=='__main__':unittest.main()
