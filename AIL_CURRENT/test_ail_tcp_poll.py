"""Batch socket readiness checked with independent clients and typed object relinking."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build
from test_ail_tcp_listener import RunningServer

BOUNDS=r'''struct Box { peers:list[tcpsocket]; masks:list[int]; }
fn replace(box:Box)->list[int] { box.peers=[]; return box.masks; }
fn change(box:Box)->int { box.masks[0]=2; return 0; }
fn main()->int {
 let empty:list[tcpsocket]=[];
 if len(tcp_poll(empty,[],-1))!=0 or len(tcp_poll(empty,[],0))!=0 or len(tcp_poll(empty,[],2147483647))!=0 { return 8; }
 let listener=tcp_listen("127.0.0.1",0,1); let peers=[listener];
 let ignored=tcp_poll(peers,[0],-1); if len(ignored)!=1 or ignored[0]!=0 { return 9; }
 let noevent=tcp_poll(peers,[1],1); if noevent[0]!=0 { return 10; }
 let box=Box([tcp_listen("127.0.0.1",0,1)],[1]);
 let captured=tcp_poll(box.peers,replace(box),0);
 if len(captured)!=1 or captured[0]!=0 or len(box.peers)!=0 { return 11; }
 let copied=tcp_poll(peers,box.masks,change(box));
 if copied[0]!=0 or box.masks[0]!=2 { return 12; }
 let lazy=tcp_poll(peers,[1],-1) if len(sys.argv)==2 else [7];
 if len(lazy)!=1 or lazy[0]!=7 { return 13; }
 let caught:int=0;
 try { tcp_poll(peers,[1],-2); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[1],2147483648); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[-1],0); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[4],0); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[2],0); } except OSError { caught+=1; }
 try { tcp_poll(peers,[3],0); } except OSError { caught+=1; }
 try { tcp_poll(peers,[],0); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[1,1],0); } except ValueError { caught+=1; }
 listener.close();
 try { tcp_poll(peers,[1],0); } except ValueError { caught+=1; }
 try { tcp_poll(peers,[0],0); } except ValueError { caught+=1; }
 print(caught); return 0;
}'''

SERVER=r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,2); print(listener.local_port()); flush_stdout();
 let accepted=tcp_poll([listener],[1],5000); if accepted[0]!=1 { return 8; }
 let first=listener.accept(); let second=listener.accept(); listener.close();
 let peers=[first,second]; first.set_blocking(0); second.set_blocking(0);
 let ready=tcp_poll(peers,[1,1],5000);
 if ready[0]!=0 or ready[1]!=1 { return 9; }
 if second.recv(1)!=b"B" { return 10; }
 let write=tcp_poll(peers,[0,2],5000);
 if write[0]!=0 or write[1]!=2 { return 11; }
 second.send(b"second"); second.shutdown_write();
 let ended=tcp_poll(peers,[0,1],5000);
 if ended[0]!=0 or ended[1]!=1 or second.recv(1)!=b"" { return 12; }
 let last=tcp_poll(peers,[1,0],-1); if last[0]!=1 or last[1]!=0 { return 13; }
 if first.recv(1)!=b"A" { return 14; }
 first.close(); second.close(); print("done"); return 0;
}'''

class TcpPollTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def test_empty_ignore_bounds_snapshot_argument_lifetime_and_lazy_conditional(self):
        exe=build(self,'bounds',BOUNDS)
        result=subprocess.run([str(exe)],capture_output=True,timeout=15)
        self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'10\n',b''))

    def test_read_write_ignore_eof_and_infinite_wait(self):
        exe=build(self,'batch',SERVER)
        with RunningServer(exe) as server:
            first=socket.create_connection(('127.0.0.1',server.port),timeout=8)
            second=socket.create_connection(('127.0.0.1',server.port),timeout=8)
            try:
                first.settimeout(8); second.settimeout(8); second.sendall(b'B')
                output=bytearray()
                while chunk:=second.recv(4096): output.extend(chunk)
                self.assertEqual(bytes(output),b'second')
                first.sendall(b'A'); second.shutdown(socket.SHUT_WR)
                self.assertEqual(first.recv(1),b'')
                out,err=server.finish()
            finally:
                first.close(); second.close()
        self.assertEqual((out.replace(b'\r\n',b'\n'),err),(b'done\n',b''))

    def test_source_free_numeric_result_and_preserved_objects(self):
        provider='fn wait_one(peers:list[tcpsocket])->list[int] { return tcp_poll(peers,[1],5000); }'
        obj=self.ail_build('provider',provider,library=True)
        folder=self.root/'moved poll provider 😀'; folder.mkdir(); moved=folder/obj.name
        shutil.move(obj,moved); shutil.move(str(obj)+'.json',str(moved)+'.json'); before=self.snapshot(moved)
        entry=r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,1); print(listener.local_port()); flush_stdout();
 let ready=wait_one([listener]); if len(ready)!=1 or ready[0]!=1 { return 8; }
 let peer=listener.accept(); listener.close(); peer.send(b"poll object"); peer.close(); print(ready[0]); return 0;
}'''
        exe=self.ail_build('entry',entry,moved)
        with RunningServer(exe) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:
                output=bytearray()
                while chunk:=peer.recv(4096): output.extend(chunk)
            self.assertEqual(bytes(output),b'poll object'); out,err=server.finish()
        self.assertEqual((out.replace(b'\r\n',b'\n'),err),(b'1\n',b'')); self.assertEqual(self.snapshot(moved),before)

    def test_wrong_shapes_and_shadowed_names(self):
        cases=('tcp_poll();','tcp_poll(1,[1],0);','tcp_poll([],1,0);',
               'let peers:list[tcpsocket]=[]; tcp_poll(peers,[1.5],0);',
               'let peers:list[tcpsocket]=[]; tcp_poll(peers,[],1.5);',
               'let peers:list[tcpsocket]=[]; tcp_poll(peers,[],milliseconds=0);')
        for i,statement in enumerate(cases):
            with self.subTest(statement=statement):
                path=self.write(f'bad{i}.ail','fn main()->int { '+statement+'return 0; }'); output=self.root/f'bad{i}'
                result=self.command('compile',path,'-o',output)
                self.assertNotEqual(result.returncode,0); self.assertNotIn(b'Traceback',result.stderr)
                self.assertFalse(output.exists()); self.assertFalse(output.with_suffix('.exe').exists())
        for i,source in enumerate(('fn tcp_poll(n:int)->int { return n+11; } fn main()->int { print(tcp_poll(5)); return 0; }',
                                   'fn other(n:int)->int { return n+11; } fn main()->int { let tcp_poll:Callable[[int],int]=other; print(tcp_poll(5)); return 0; }')):
            exe=build(self,f'shadow{i}',source)
            result=subprocess.run([str(exe)],capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout.replace(b'\r\n',b'\n'),result.stderr),(0,b'16\n',b''))

if __name__=='__main__': unittest.main()