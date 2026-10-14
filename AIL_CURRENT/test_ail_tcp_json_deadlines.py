"""Peer expiry despite healthy traffic, batch deadline and optional CLI boundaries."""
import shutil
import socket
import subprocess
import time
import unittest
import test_ail_c_objects as support
from test_ail_tcp_listener import RunningServer
from test_ail_tcp_json_lines_poll import SOURCES, EXAMPLES

class JsonDeadlineTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    def server(self):
        for name in SOURCES:shutil.copy2(EXAMPLES/name,self.root/name)
        exe=self.root/'timed.exe';result=self.command('compile',self.root/SOURCES[-1],'-o',exe)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'));return exe
    def connect(self,server):
        peer=socket.create_connection(('127.0.0.1',server.port),timeout=5);peer.settimeout(5);return peer
    def exchange(self,peer,wire):
        peer.sendall(wire);out=bytearray()
        while out.count(b'\n')<wire.count(b'\n'):
            chunk=peer.recv(8192);self.assertTrue(chunk,'missing response');out.extend(chunk)
        self.assertEqual(bytes(out),wire)
    def result(self,server):
        out,err=server.process.communicate(timeout=5)
        self.assertEqual((server.process.returncode,out),(3,b''));self.assertIn(b'deadline',err)
    def test_idle_peer_expires_while_other_peer_progresses(self):
        exe=self.server()
        with RunningServer(exe,('127.0.0.1',0,2,3000,128,2,200,3000)) as server:
            with self.connect(server) as idle,self.connect(server) as active:
                began=time.monotonic()
                for i in range(16):
                    self.exchange(active,f'{i}\n'.encode());time.sleep(.025)
                idle.settimeout(1);self.assertEqual(idle.recv(1),b'')
                self.assertLess(time.monotonic()-began,2)
                self.exchange(active,b'null\n');active.shutdown(socket.SHUT_WR);self.assertEqual(active.recv(1),b'')
            self.result(server)
    def test_whole_batch_expires_under_continued_traffic(self):
        exe=self.server()
        with RunningServer(exe,('127.0.0.1',0,1,3000,128,1,0,300)) as server:
            with self.connect(server) as active:
                began=time.monotonic();sent=0;received=bytearray()
                while time.monotonic()-began<2:
                    try:active.sendall(b'null\n');sent+=1;chunk=active.recv(8192)
                    except OSError:break
                    if not chunk:break
                    received.extend(chunk);time.sleep(.015)
                self.assertGreater(len(received),0)
                self.assertEqual(bytes(received),b'null\n'*(len(received)//5))
                self.assertLessEqual(len(received),sent*5)
                self.assertLess(time.monotonic()-began,2)
            self.result(server)
    def test_zero_disables_and_invalid_deadline_arguments(self):
        exe=self.server()
        with RunningServer(exe,('127.0.0.1',0,1,1000,64,1,0,0)) as server:
            with self.connect(server) as peer:
                self.exchange(peer,b'{}\n');peer.shutdown(socket.SHUT_WR);self.assertEqual(peer.recv(1),b'')
            out,err=server.finish();self.assertEqual((out.strip(),err),(b'1',b''))
        base=['127.0.0.1','0','1','1000','64','1','0','0']
        for index,value in ((6,'-1'),(6,'2147483648'),(7,'-1'),(7,'2147483648'),(7,'9223372036854775808')):
            args=base.copy();args[index]=value;result=subprocess.run([str(exe),*args],capture_output=True,timeout=5)
            self.assertEqual((result.returncode,result.stdout),(4,b''));self.assertTrue(result.stderr)
        result=subprocess.run([str(exe),*base[:-1]],capture_output=True,timeout=5)
        self.assertEqual((result.returncode,result.stdout),(2,b''))

if __name__=='__main__':unittest.main()