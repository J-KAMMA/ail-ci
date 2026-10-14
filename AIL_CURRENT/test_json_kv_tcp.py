"""Independent clients verify complete KV batches and persisted state over TCP."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import test_ail_c_objects as support
from test_ail_tcp_listener import RunningServer
from test_json_kv import reference

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('gcc'),'C compiler required')
class JsonKvTcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix='ail-kv-tcp-');cls.addClassCleanup(temporary.cleanup)
        cls.root=Path(temporary.name);exe=cls.root/'server'
        result=subprocess.run([sys.executable,'-X','utf8','-B',support.ROOT/'ail_chatgpt.py','compile',support.ROOT/'language_examples/json_kv_tcp_main.ail','-o',exe],capture_output=True,timeout=180)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        cls.exe=exe if exe.is_file() else exe.with_suffix('.exe')

    def exchange(self,port,data,chunk=8192):
        with socket.create_connection(('127.0.0.1',port),timeout=5) as peer:
            peer.settimeout(15)
            for offset in range(0,len(data),chunk):peer.sendall(data[offset:offset+chunk])
            peer.shutdown(socket.SHUT_WR)
            output=bytearray()
            while piece:=peer.recv(8192):output.extend(piece)
            return bytes(output)

    def test_fragmented_utf8_persistence_and_multiple_connections(self):
        db=self.root/'state 日本😀.json';current=None;total=0
        batches=[b'{"op":"set","key":"k","value":"v"}\r\n{"op":"count"}',
                 ('{"op":"set","key":"日本😀","value":"line\\nvalue"}\n{"op":"get","key":"日本😀"}').encode(),
                 b'{"op":"delete","key":"k"}\n{"op":"get","key":"k"}\n{"op":"count"}\n']
        with RunningServer(self.exe,(0,db,len(batches),3000)) as server:
            for data in batches:
                expected,snapshot=reference(current,data)
                self.assertEqual(self.exchange(server.port,data,1),expected)
                self.assertEqual(db.read_bytes(),snapshot);current=snapshot.decode();total+=expected.count(b'\n')
            self.assertEqual(server.finish(),(f'{total}{os.linesep}'.encode(),b''))
        self.assertFalse(Path(str(db)+'.ail-stage').exists())
        with RunningServer(self.exe,(0,db,1,3000)) as server:
            data=b'{"op":"get","key":"'+'日本😀'.encode()+b'"}'
            expected,snapshot=reference(current,data);self.assertEqual(self.exchange(server.port,data),expected)
            self.assertEqual(server.finish(),(f'1{os.linesep}'.encode(),b''));self.assertEqual(db.read_bytes(),snapshot)

    def test_invalid_batch_and_wait_failure_preserve_state(self):
        for index,data in enumerate((b'{"op":"set","key":"x","value":"y"}\ninvalid',b'\xff',b'{"op":"count","op":"count"}',b'\n'*8193)):
            db=self.root/f'bad{index}.json';db.write_bytes(b'{"kept":"original"}')
            with RunningServer(self.exe,(0,db,1,1000)) as server:
                self.assertEqual(self.exchange(server.port,data),b'')
                out,err=server.process.communicate(timeout=5)
                self.assertEqual((server.process.returncode,out),(4,b''));self.assertTrue(err)
            self.assertEqual(db.read_bytes(),b'{"kept":"original"}');self.assertFalse(Path(str(db)+'.ail-stage').exists())
        db=self.root/'timeout.json';db.write_bytes(b'{}')
        with RunningServer(self.exe,(0,db,1,100)) as server:
            with socket.create_connection(('127.0.0.1',server.port),timeout=5) as peer:
                peer.settimeout(5);peer.sendall(b'{');self.assertEqual(peer.recv(1),b'')
            out,err=server.process.communicate(timeout=5);self.assertEqual((server.process.returncode,out),(3,b''));self.assertTrue(err)
        self.assertEqual(db.read_bytes(),b'{}')

    def test_large_replies_and_invalid_cli_configuration(self):
        db=self.root/'large.json';value='😀'*4096
        commands=[{'op':'set','key':'k','value':value}]+[{'op':'get','key':'k'}]*20
        data=('\n'.join(json.dumps(row,ensure_ascii=False) for row in commands)).encode();expected,snapshot=reference(None,data)
        with RunningServer(self.exe,(0,db,1,3000)) as server:
            self.assertEqual(self.exchange(server.port,data,7),expected);self.assertEqual(server.finish(),(f'21{os.linesep}'.encode(),b''))
        self.assertEqual(db.read_bytes(),snapshot)
        for args in (('0',db,'0','1'),('0',db,'4097','1'),('0',db,'1','0'),('0',db,'1','2147483648'),('-1',db,'1','1'),('65536',db,'1','1')):
            result=subprocess.run([self.exe,*map(str,args)],capture_output=True,timeout=5)
            self.assertEqual((result.returncode,result.stdout),(4,b''));self.assertEqual(db.read_bytes(),snapshot)

if __name__=='__main__':unittest.main()