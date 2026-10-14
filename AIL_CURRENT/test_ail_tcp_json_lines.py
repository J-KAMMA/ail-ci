"""Bounded JSON-lines service checked by independent Python JSON/socket clients."""
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
           'checked_integer.ail', 'tcp_json_lines.ail', 'tcp_json_lines_main.ail')


class TcpJsonLinesTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command

    def build_server(self):
        for name in SOURCES:
            shutil.copy2(EXAMPLES / name, self.root / name)
        exe = self.root / 'json-lines.exe'
        result = self.command('compile', self.root / SOURCES[-1], '-o', exe)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return exe

    def exchange(self, server, pieces):
        with socket.create_connection(('127.0.0.1', server.port), timeout=5) as peer:
            peer.settimeout(5)
            # Receive each complete frame before uploading another large frame.
            result = bytearray()
            expected_lines = 0
            for piece in pieces:
                peer.sendall(piece)
                expected_lines += piece.count(b'\n')
                while result.count(b'\n') < expected_lines:
                    chunk = peer.recv(8192)
                    self.assertTrue(chunk, 'EOF before response')
                    result.extend(chunk)
            peer.shutdown(socket.SHUT_WR)
            self.assertEqual(peer.recv(1), b'')
            return bytes(result)

    def test_frames_fragmented_utf8_large_and_sequential_clients(self):
        exe = self.build_server()
        frames = [b' { "duplicate":1,"duplicate":-0.00e+02 }\r',
                  '["日本語😀",true,null,{},[]]'.encode(),
                  ('"' + 'a' * 65536 + '"').encode(), b'"\\u0000\\t\\n"']
        expected = b''.join((render(document(frame)) + '\n').encode() for frame in frames)
        with RunningServer(exe, ('127.0.0.1', 0, 2, 3000, 1048576)) as server:
            pieces = [frames[0] + b'\n', frames[1][:3], frames[1][3:7], frames[1][7:] + b'\n',
                      frames[2] + b'\n', frames[3] + b'\n']
            self.assertEqual(self.exchange(server, pieces), expected)
            self.assertEqual(self.exchange(server, []), b'')
            out, err = server.finish()
        self.assertEqual(out.replace(b'\r\n', b'\n'), b'4\n')
        self.assertEqual(err, b'')
        # Exactly the cap succeeds, including across recv chunk boundaries.
        with RunningServer(exe, ('127.0.0.1', 0, 1, 3000, 4)) as server:
            self.assertEqual(self.exchange(server, [b'n', b'ull\n']), b'null\n')
            self.assertEqual(server.finish()[0].strip(), b'1')
        with RunningServer(exe, ('127.0.0.1', 0, 1, 3000, 64)) as server:
            self.assertEqual(self.exchange(server, [b'null\ntrue\n{}\n']), b'null\ntrue\n{}\n')
            self.assertEqual(server.finish()[0].strip(), b'3')

    def test_refused_frames_arguments_and_readiness_deadlines(self):
        exe = self.build_server()
        for data, cap in ((b'nullx\n', 4), (b'null', 64), (b'\n', 64),
                          (b'{bad}\n', 64), (b'"\xff"\n', 64), (b'"\\ud800"\n', 64)):
            with self.subTest(data=data):
                with RunningServer(exe, ('127.0.0.1', 0, 1, 3000, cap)) as server:
                    with socket.create_connection(('127.0.0.1', server.port), timeout=5) as peer:
                        peer.sendall(data)
                        peer.shutdown(socket.SHUT_WR)
                        try:
                            self.assertEqual(peer.recv(1), b'')
                        except ConnectionResetError:
                            pass
                    out, err = server.process.communicate(timeout=5)
                    self.assertEqual(server.process.returncode, 4, err)
                    self.assertEqual(out, b'')
                    self.assertIn(b'invalid', err)
        for connect in (False, True):
            with RunningServer(exe, ('127.0.0.1', 0, 1, 100, 64)) as server:
                peer = socket.create_connection(('127.0.0.1', server.port), timeout=5) if connect else None
                try:
                    out, err = server.process.communicate(timeout=5)
                finally:
                    if peer is not None:
                        peer.close()
                self.assertEqual(server.process.returncode, 3, err)
                self.assertEqual(out, b'')
                self.assertIn(b'deadline', err)
        # A recipient that never reads must not trap a blocking whole-buffer send.
        with RunningServer(exe, ('127.0.0.1', 0, 1, 200, 1048576)) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer:
                peer.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                peer.settimeout(5)
                peer.connect(('127.0.0.1', server.port))
                frame = b'"' + b'a' * (1048576 - 2) + b'"\n'
                failures = []
                def upload():
                    try:
                        peer.sendall(frame * 8)
                    except OSError as error:
                        failures.append(error)
                sender = threading.Thread(target=upload, daemon=True)
                sender.start()
                out, err = server.process.communicate(timeout=8)
                try:
                    peer.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sender.join(6)
                self.assertFalse(sender.is_alive(), 'client upload did not finish')
                self.assertEqual(server.process.returncode, 3, err)
                self.assertEqual(out, b'')
                self.assertIn(b'deadline', err)
        for args, code in (((), 2), (('127.0.0.1', 0, 0, 1, 1), 4),
                           (('127.0.0.1', 0, 1, 0, 1), 4),
                           (('127.0.0.1', 0, 1, 2147483648, 1), 4),
                           (('127.0.0.1', 0, 1, 1, 0), 4),
                           (('127.0.0.1', 0, 1, 1, 1048577), 4),
                           (('127.0.0.1', 65536, 1, 1, 1), 4),
                           (('127.0.0.1', 0, 9223372036854775808, 1, 1), 4)):
            result = subprocess.run([str(exe), *map(str, args)], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()