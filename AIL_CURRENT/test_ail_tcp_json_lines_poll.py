"""Multiplexed bounded JSON Lines, with independent Python socket/JSON peers."""
import shutil
import socket
import subprocess
import threading
import unittest
from pathlib import Path

import test_ail_c_objects as support
from test_ail_tcp_listener import RunningServer
from test_json_query_cli import document, render

EXAMPLES = support.ROOT / 'language_examples'
SOURCES = ('json_text.ail', 'json_document.ail', 'json_tree.ail', 'json_pointer.ail',
           'checked_integer.ail', 'tcp_json_lines_poll.ail', 'tcp_json_lines_poll_main.ail')


class TcpJsonLinesPollTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command

    def build_server(self):
        for name in SOURCES:
            shutil.copy2(EXAMPLES / name, self.root / name)
        exe = self.root / 'json-poll.exe'
        result = self.command('compile', self.root / SOURCES[-1], '-o', exe)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return exe

    def connect(self, server):
        peer = socket.create_connection(('127.0.0.1', server.port), timeout=5)
        peer.settimeout(5)
        return peer

    def receive(self, peer, lines):
        result = bytearray()
        while result.count(b'\n') < lines:
            chunk = peer.recv(8192)
            self.assertTrue(chunk, 'response ended early')
            result.extend(chunk)
        return bytes(result)

    def finish(self, server, code, count=None):
        out, err = server.process.communicate(timeout=8)
        self.assertEqual(server.process.returncode, code, err)
        self.assertEqual(out.replace(b'\r\n', b'\n'), b'' if count is None else f'{count}\n'.encode())
        if code == 0:
            self.assertEqual(err, b'')
        else:
            self.assertTrue(err)

    def test_idle_first_peer_does_not_hold_second_and_fragmented_frames(self):
        exe = self.build_server()
        frame = '["日本語😀",-0.00e+02,{"x":1,"x":2}]'.encode()
        expected = (render(document(frame)) + '\n').encode() + b'true\n{}\n'
        with RunningServer(exe, ('127.0.0.1', 0, 2, 2000, 1048576, 2)) as server:
            with self.connect(server) as stalled, self.connect(server) as second:
                second.sendall(frame[:3]); second.sendall(frame[3:7]); second.sendall(frame[7:] + b'\ntrue\n{}\n')
                self.assertEqual(self.receive(second, 3), expected)
                large = b'"' + b'x' * 65536 + b'"\n'
                second.sendall(large)
                self.assertEqual(self.receive(second, 1), large)
                second.shutdown(socket.SHUT_WR)
                self.assertEqual(second.recv(1), b'')
                stalled.shutdown(socket.SHUT_WR)
                self.assertEqual(stalled.recv(1), b'')
            self.finish(server, 0, 4)
        # Slot reuse and MAX_ACTIVE=1 still accept all target clients.
        with RunningServer(exe, ('127.0.0.1', 0, 3, 2000, 4, 1)) as server:
            for _ in range(3):
                with self.connect(server) as peer:
                    peer.sendall(b'n'); peer.sendall(b'ull\n')
                    self.assertEqual(self.receive(peer, 1), b'null\n')
                    peer.shutdown(socket.SHUT_WR)
                    self.assertEqual(peer.recv(1), b'')
            self.finish(server, 0, 3)

    def test_nonreading_peer_does_not_hold_another_reply(self):
        exe = self.build_server()
        with RunningServer(exe, ('127.0.0.1', 0, 2, 300, 1048576, 2)) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stalled:
                stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                stalled.settimeout(5)
                stalled.connect(('127.0.0.1', server.port))
                frame = b'"' + b'a' * (1048576 - 2) + b'"\n'
                def upload():
                    try:
                        stalled.sendall(frame * 8)
                    except OSError:
                        pass
                sender = threading.Thread(target=upload, daemon=True)
                sender.start()
                with self.connect(server) as peer:
                    peer.sendall(b'{"other":true}\n')
                    self.assertEqual(self.receive(peer, 1), b'{"other":true}\n')
                    peer.shutdown(socket.SHUT_WR)
                    self.assertEqual(peer.recv(1), b'')
                # Leave the recipient stalled: only the batch idle deadline ends it.
                self.finish(server, 3)
                try:
                    stalled.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sender.join(6)
                self.assertFalse(sender.is_alive(), 'client uploader did not finish')

    def test_invalid_peer_isolated_and_cap_eof_utf8(self):
        exe = self.build_server()
        for bad, cap in ((b'nullx\n', 4), (b'null', 64), (b'\n', 64),
                         (b'{bad}\n', 64), (b'"\xff"\n', 64), (b'"\\ud800"\n', 64)):
            with self.subTest(bad=bad):
                with RunningServer(exe, ('127.0.0.1', 0, 2, 2000, cap, 2)) as server:
                    with self.connect(server) as broken, self.connect(server) as healthy:
                        broken.sendall(bad); broken.shutdown(socket.SHUT_WR)
                        healthy.sendall(b'null\n')
                        self.assertEqual(self.receive(healthy, 1), b'null\n')
                        healthy.shutdown(socket.SHUT_WR)
                        self.assertEqual(healthy.recv(1), b'')
                        try:
                            self.assertEqual(broken.recv(1), b'')
                        except ConnectionResetError:
                            pass
                    self.finish(server, 4)

    def test_batch_idle_and_cli_bounds(self):
        exe = self.build_server()
        with RunningServer(exe, ('127.0.0.1', 0, 1, 50, 64, 1)) as server:
            self.finish(server, 3)
        defaults = ['127.0.0.1', '0', '1', '1', '64', '1']
        cases = [([], 2)]
        for index, value in ((1, '-1'), (1, '65536'), (2, '0'), (2, '9223372036854775808'),
                             (3, '0'), (3, '2147483648'), (4, '0'), (4, '1048577'),
                             (5, '0'), (5, '1025')):
            args = defaults.copy(); args[index] = value; cases.append((args, 4))
        for args, code in cases:
            result = subprocess.run([str(exe), *args], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()