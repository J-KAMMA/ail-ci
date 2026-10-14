"""Public handle lists: independent full-byte/cursor/socket oracles and relinking."""
import json
import os
import sys
import socket
import shutil
import subprocess
from pathlib import Path
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build
from test_ail_tcp_listener import RunningServer

BUFFERS = r'''struct Buffers { values:list[bytearray]; }
fn pack(data:bytes)->list[bytearray] {
 let values:list[bytearray]=[bytearray(data),bytearray(b"tail")]; return values;
}
fn echo(values:list[bytearray])->list[bytearray] { return values; }
fn main()->int {
 let values=pack(read_bytes(sys.argv[1]));
 let callback:Callable[[list[bytearray]],list[bytearray]]=echo;
 let holder=Buffers(callback(values)); values[0].append(0);
 let copied=list(values); let backward=values[::-1];
 values.extend(values); let kept=holder.values[-2]; values[-2]=kept;
 let moved=backward.pop(); holder.values.clear();
 copied[1]=moved; copied.reverse(); let total:int=0;
 for buffer in copied { total+=len(buffer); }
 let caught:int=0;
 try { values.pop(); } except IndexError { caught+=1; }
 try { copied[-9223372036854775808]; } except IndexError { caught+=1; }
 try { copied[9223372036854775807]; } except IndexError { caught+=1; }
 try { copied[::0]; } except ValueError { caught+=1; }
 let tiny=copied[::9223372036854775807];
 let negative=copied[::-9223372036854775808];
 if len(tiny)!=1 or len(negative)!=1 { return 9; }
 let many:list[bytearray]=[]; for i in range(17) { many.append(kept); }
 if len(many)!=17 { return 10; } many.clear();
 copied.clear(); kept.append(255);
 write_stdout_bytes((str(total)+" "+str(caught)+"\n").encode("utf-8"));
 write_stdout_bytes(bytes(moved)); return 0;
}'''

FILES = r'''struct Files { values:list[binaryfile]; }
fn wrap(peer:binaryfile)->list[binaryfile] { return [peer]; }
fn identity(values:list[binaryfile])->list[binaryfile] { return values; }
fn main()->int {
 let file=open_binary(sys.argv[1],"rb");
 let callback:Callable[[list[binaryfile]],list[binaryfile]]=identity;
 let values=callback(wrap(file)); let holder=Files(values);
 let copied=list(holder.values); let kept=copied.pop(); values.clear();
 write_stdout_bytes(file.read(1)); write_stdout_bytes(kept.read(2));
 let again:list[binaryfile]=[kept]; again.extend(again);
 let tail=again[-1]; again[0]=tail; let reverse=again[::-1]; again.clear();
 for stream in reverse { write_stdout_bytes(stream.read(3)); }
 reverse.clear(); tail.close();
 if file.closed!=1 or kept.closed!=1 { return 8; }
 try { kept.read(1); } except ValueError { return 0; }
 return 9;
}'''

SOCKETS = r'''struct Connections { peers:list[tcpsocket]; }
fn wrap(peer:tcpsocket)->list[tcpsocket] { return [peer]; }
fn echo(values:list[tcpsocket])->list[tcpsocket] { return values; }
fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,4); let listeners=wrap(listener);
 print(listeners[0].local_port()); flush_stdout();
 let peers:list[tcpsocket]=[];
 for i in range(2) { peers.append(listeners[0].accept()); }
 let callback:Callable[[list[tcpsocket]],list[tcpsocket]]=echo;
 let holder=Connections(callback(peers)); let copied=list(holder.peers);
 holder.peers.clear(); listeners.pop().close();
 if listener.closed!=1 { return 9; }
 let total:int=0;
 for peer in copied {
  while True { let chunk=peer.recv(8192); if len(chunk)==0 { break; } peer.send(chunk); total+=len(chunk); }
  peer.shutdown_write(); peer.close();
 }
 copied.clear(); print(total); return 0;
}'''

FIELD_PROVIDER=r'''struct Handles {
 buffers:list[bytearray]; files:list[binaryfile]; peers:list[tcpsocket];
 transform:Callable[[list[bytearray]],list[bytearray]];
}
fn clone(values:list[bytearray])->list[bytearray] { return list(values); }
fn make(file:binaryfile,peer:tcpsocket)->Handles {
 return Handles([bytearray(b"prefix\0")],[file],[peer],clone);
}'''

FIELD_ENTRY=r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,1); print(listener.local_port()); flush_stdout();
 let owner=make(open_binary(sys.argv[1],"rb"),listener.accept()); listener.close();
 let values=owner.transform(owner.buffers); let prefix=values.pop();
 let file=owner.files.pop(); let peer=owner.peers[0];
 owner.buffers.clear(); owner.files.clear(); owner.peers.clear(); values.clear();
 peer.send(bytes(prefix)); let total:int=len(prefix);
 while True { let data=file.read(8192); if len(data)==0 { break; } peer.send(data); total+=len(data); }
 file.close(); peer.close(); print(total); return 0;
}'''

class HandleListTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    snapshot=support.CObjectTests.snapshot

    def test_buffer_spines_elements_fields_callback_widths_and_full_bytes(self):
        exe=build(self,'buffers',BUFFERS)
        path=self.root/'binary.bin'
        for data in (b'',b'\x00\xff',bytes(range(256))*257):
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                result=subprocess.run([str(exe),str(path)],capture_output=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stderr[:2000])
                self.assertEqual(result.stderr,b'')
                self.assertEqual(result.stdout,f'{2*(len(data)+1)} 4\n'.encode()+data+b'\x00\xff')
                self.assertEqual(path.read_bytes(),data)

    def test_file_cursor_shared_after_list_clear_and_alias_close(self):
        exe=build(self,'files',FILES)
        path=self.root/'input.bin'
        for data in (b'',b'abcdefghi',bytes(range(256))):
            path.write_bytes(data)
            result=subprocess.run([str(exe),str(path)],capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr[:2000])
            self.assertEqual((result.stdout,result.stderr),(data[:9],b''))
            self.assertEqual(path.read_bytes(),data)

    def test_two_connections_retained_in_lists_and_shared_listener_close(self):
        exe=build(self,'sockets',SOCKETS)
        payloads=(bytes(range(256))*17+b'\0\xff',b'second connection\0')
        with RunningServer(exe) as server:
            clients=[socket.create_connection(('127.0.0.1',server.port),timeout=8) for _ in payloads]
            try:
                for peer,data in zip(clients,payloads):
                    peer.settimeout(8); peer.sendall(data); peer.shutdown(socket.SHUT_WR)
                for peer,data in zip(clients,payloads):
                    output=bytearray()
                    while chunk:=peer.recv(4096): output.extend(chunk)
                    self.assertEqual(bytes(output),data)
            finally:
                for peer in clients: peer.close()
            out,err=server.finish()
        self.assertEqual(out.replace(b'\r\n',b'\n'),f'{sum(map(len,payloads))}\n'.encode())
        self.assertEqual(err,b'')

    def test_source_free_relocated_handles_and_callbacks(self):
        for name,provider,main in (
            ('buffer','fn make()->list[bytearray] { return [bytearray(b"abc")]; }\n'
                      'fn echo(xs:list[bytearray])->list[bytearray] { return xs; }',
             'fn main()->int { let cb:Callable[[list[bytearray]],list[bytearray]]=echo; let xs=cb(make()); let kept=xs.pop(); xs.clear(); write_stdout_bytes(bytes(kept)); return 0; }'),
            ('file','fn make(path:str)->list[binaryfile] { return [open_binary(path,"rb")]; }',
             'fn main()->int { let xs=make(sys.argv[1]); let kept=xs.pop(); xs.clear(); write_stdout_bytes(kept.read(100)); kept.close(); return 0; }')):
            with self.subTest(kind=name):
                obj=self.ail_build(name,provider,library=True)
                metadata=json.loads(Path(str(obj)+'.json').read_text())
                self.assertIn('handle_list:',json.dumps(metadata))
                folder=self.root/(name+' moved'); folder.mkdir(); moved=folder/obj.name
                shutil.move(obj,moved); shutil.move(str(obj)+'.json',str(moved)+'.json')
                before=self.snapshot(moved)
                exe=self.ail_build(name+'entry',main,moved)
                path=self.root/(name+'.bin'); path.write_bytes(b'abc')
                result=subprocess.run([str(exe),str(path)],capture_output=True,timeout=20)
                self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'abc',b''))
                self.assertEqual(self.snapshot(moved),before)

    def test_source_free_relocated_socket_list(self):
        provider = 'fn wrap(peer:tcpsocket)->list[tcpsocket] { return [peer]; }\n'
        provider += 'fn identity(peers:list[tcpsocket])->list[tcpsocket] { return peers; }'
        obj=self.ail_build('socket-provider',provider,library=True)
        folder=self.root/'moved socket list'; folder.mkdir(); moved=folder/obj.name
        shutil.move(obj,moved); shutil.move(str(obj)+'.json',str(moved)+'.json')
        before=self.snapshot(moved)
        entry=r'''fn main()->int {
 let listener=tcp_listen("127.0.0.1",0,1); print(listener.local_port()); flush_stdout();
 let cb:Callable[[list[tcpsocket]],list[tcpsocket]]=identity;
 let peers=cb(wrap(listener.accept())); listener.close();
 let kept=peers.pop(); peers.clear(); let total:int=0;
 while True { let data=kept.recv(8192); if len(data)==0 { break; } kept.send(data); total+=len(data); }
 kept.close(); print(total); return 0;
}'''
        exe=self.ail_build('socket-entry',entry,moved)
        data=bytes(range(256))*33+b'\0\xff'
        with RunningServer(exe) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:
                peer.settimeout(8); peer.sendall(data); peer.shutdown(socket.SHUT_WR); output=bytearray()
                while chunk:=peer.recv(4096): output.extend(chunk)
            self.assertEqual(bytes(output),data)
            out,err=server.finish()
        self.assertEqual(out.replace(b'\r\n',b'\n'),f'{len(data)}\n'.encode())
        self.assertEqual(err,b''); self.assertEqual(self.snapshot(moved),before)

    def test_source_free_struct_fields_all_three_kinds_and_callback(self):
        provider=FIELD_PROVIDER
        obj=self.ail_build('handles-provider',provider,library=True)
        folder=self.root/'moved all handle fields'; folder.mkdir(); moved=folder/obj.name
        shutil.move(obj,moved); shutil.move(str(obj)+'.json',str(moved)+'.json')
        before=self.snapshot(moved)
        entry=FIELD_ENTRY
        exe=self.ail_build('handles-entry',entry,moved)
        data=bytes(range(256))*33+b'\0\xff'
        path=self.root/'payload.bin'; path.write_bytes(data)
        with RunningServer(exe,(path,)) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=8) as peer:
                peer.settimeout(8); output=bytearray()
                while chunk:=peer.recv(4096): output.extend(chunk)
            self.assertEqual(bytes(output),b'prefix\0'+data)
            out,err=server.finish()
        self.assertEqual(out.replace(b'\r\n',b'\n'),f'{len(data)+7}\n'.encode())
        self.assertEqual(err,b''); self.assertEqual(self.snapshot(moved),before)
        self.assertEqual(path.read_bytes(),data)

    def test_runtime_capacity_and_span_rejected_before_pointer_access(self):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            from pipeline import compiler
            runtime=to_c('def anchor()->int:\n a:list[bytearray]=[]\n f:list[binaryfile]=[]\n s:list[tcpsocket]=[]\n return len(a)+len(f)+len(s)\n',name='anchor',strict=True,library=True)
            cc=compiler()
        finally:
            sys.path.pop(0)
        host=r'''
int main(int argc,char **argv) {
 if(argc!=3)return 2;
 uintmax_t limit=SIZE_MAX/sizeof(void *);
 if(limit>(uintmax_t)PTRDIFF_MAX/sizeof(void *))limit=(uintmax_t)PTRDIFF_MAX/sizeof(void *);
 if(limit>INT64_MAX)limit=INT64_MAX;
#define CHECK(ELEMENT) do { \
 ail_hlist_##ELEMENT destination={1,(int64_t)limit,(int64_t)limit,(ail_##ELEMENT **)16}; \
 ail_hlist_##ELEMENT source={1,1,1,(ail_##ELEMENT **)16}; \
 if(argv[2][0]=='s'){destination.n=(int64_t)(limit/2+1);ail_hlist_##ELEMENT##_extend(&destination,&destination);} \
 else if(argv[2][0]=='p')ail_hlist_##ELEMENT##_push(&destination,(ail_##ELEMENT *)1); \
 else if(argv[2][0]=='w'){destination.n=destination.cap=1;destination.p=(ail_##ELEMENT **)(UINTPTR_MAX-3);ail_hlist_##ELEMENT##_get(&destination,0);} \
 else if(argv[2][0]=='n'){destination.n=-1;ail_hlist_##ELEMENT##_len(&destination);} \
 else ail_hlist_##ELEMENT##_extend(&destination,&source); \
} while(0)
 if(argv[1][0]=='b')CHECK(bytearray);
 else if(argv[1][0]=='f')CHECK(binaryfile);
 else CHECK(tcpsocket);
 return 9;
}
'''
        path=self.write('list-limits.c',runtime+host)
        exe=self.root/('limits.exe' if os.name=='nt' else 'limits')
        flags=['-std=c11',*FLAGS,str(path),'-lm','-o',str(exe)]
        if os.name=='nt':flags.append('-lws2_32')
        else:flags.insert(0,'-D_POSIX_C_SOURCE=200809L')
        result=subprocess.run([cc,*flags],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr[:2000].decode(errors='replace'))
        for element in ('buffer','file','socket'):
            for mode in ('distinct','self','push','wrapped-span','negative'):
                with self.subTest(element=element,mode=mode):
                    result=subprocess.run([str(exe),element,mode],capture_output=True,timeout=10)
                    self.assertEqual(result.returncode,1,result.stderr[:2000])
                    self.assertEqual(result.stdout,b'')
                    self.assertTrue(b'handle list' in result.stderr,result.stderr[:2000])

    def test_owned_c_wrappers_refuse_handle_lists_and_nested_callbacks(self):
        sources = [f'fn identity(values:list[{kind}])->list[{kind}] {{ return values; }}'
                   for kind in ('bytearray','binaryfile','tcpsocket')]
        sources.append('fn consume(callback:Callable[[list[bytearray]],list[bytearray]])->int { return 0; }')
        for index,source in enumerate(sources):
            path=self.write(f'wrapper{index}.ail',source)
            output=self.root/f'wrapper{index}'
            result=self.command('compile-library',path,'--name',f'wrap{index}','-o',output)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'cannot marshal handle lists',result.stderr)
            self.assertNotIn(b'Traceback',result.stderr)
            self.assertFalse(output.exists())

    def test_python_ctypes_refuses_handle_lists_before_native_build(self):
        from unittest.mock import patch
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import compile_fn, Unsupported
            with patch('pipeline.shared_object',side_effect=AssertionError('native build forbidden')) as native:
                for kind in ('bytearray','binaryfile','tcpsocket'):
                    for source in (f'def run(values:list[{kind}])->int:\n return len(values)\n',
                                   f'def run()->list[{kind}]:\n values:list[{kind}]=[]\n return values\n'):
                        with self.subTest(kind=kind,source=source):
                            with self.assertRaisesRegex(Unsupported,'does not marshal Python handle lists'):
                                compile_fn(source)
                native.assert_not_called()
        finally:
            sys.path.pop(0)

    def test_wrong_element_mixed_list_and_sort_refused(self):
        statements=('let xs:list[bytearray]=[1];','let xs:list[binaryfile]=[bytearray()];',
                    'let xs:list[tcpsocket]=[bytearray()];',
                    'let xs:list[bytearray]=[]; xs.append(1);',
                    'let xs:list[bytearray]=[]; xs.extend([1]);',
                    'let xs:list[bytearray]=[]; let ys=sorted(xs);',
                    'let xs:list[bytearray]=[]; xs.sort();')
        for i,statement in enumerate(statements):
            with self.subTest(statement=statement):
                path=self.write(f'wrong{i}.ail','fn main()->int { '+statement+' return 0; }')
                output=self.root/f'wrong{i}'
                result=self.command('compile',path,'-o',output)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn(b'Traceback',result.stderr)
                self.assertFalse(output.exists()); self.assertFalse(output.with_suffix('.exe').exists())

if __name__=='__main__': unittest.main()