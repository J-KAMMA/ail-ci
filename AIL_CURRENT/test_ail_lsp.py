"""`tools/ail_lsp.py`: the diagnostics-only language server over stdio.

A scripted LSP client starts the server as a subprocess, opens a clean file and a file the compiler
refuses by name, checks the published diagnostics, exercises a full-sync change and save/close, and
shuts the server down.
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER = ROOT.parent / 'tools' / 'ail_lsp.py'

CLEAN = "def main():\n    print(1 + 2)\n\n\nmain()\n"
# `ys = xs` then a write through ys and a later read of xs: refused by name at line 3.
REFUSAL = ("def main():\n"
           "    xs = [1, 2]\n"
           "    ys = xs\n"
           "    ys.append(3)\n"
           "    print(xs)\n"
           "\n\n"
           "main()\n")


class Client:
    def __init__(self, cwd):
        env = dict(os.environ, PYTHONUTF8='1')
        self.process = subprocess.Popen(
            [sys.executable, '-B', str(SERVER)], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.messages = queue.Queue()
        self.next_id = 1
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        stream = self.process.stdout
        while True:
            length = None
            while True:
                line = stream.readline()
                if not line:
                    self.messages.put(None)
                    return
                if not line.strip():
                    break
                name, _, value = line.decode('ascii').partition(':')
                if name.lower() == 'content-length':
                    length = int(value)
            self.messages.put(json.loads(stream.read(length).decode('utf-8')))

    def send(self, message):
        data = json.dumps(dict(jsonrpc='2.0', **message)).encode('utf-8')
        self.process.stdin.write(b'Content-Length: %d\r\n\r\n' % len(data) + data)
        self.process.stdin.flush()

    def request(self, method, params=None):
        identifier, self.next_id = self.next_id, self.next_id + 1
        self.send({'id': identifier, 'method': method, 'params': params or {}})
        return self.until(lambda message: message.get('id') == identifier)

    def notify(self, method, params=None):
        self.send({'method': method, 'params': params or {}})

    def until(self, predicate, timeout=120):
        while True:
            message = self.messages.get(timeout=timeout)
            if message is None:
                raise AssertionError('the server closed its output')
            if predicate(message):
                return message

    def diagnostics(self, uri, version=None, expected=None):
        message = self.until(lambda item: item.get('method') == 'textDocument/publishDiagnostics'
                             and item['params']['uri'] == uri
                             and (version is None or item['params'].get('version') == version)
                             and (expected is None or item['params']['diagnostics'] == expected))
        return message['params']['diagnostics']

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


class LspTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-lsp-test-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.client = Client(self.dir)
        self.addCleanup(self.client.close)
        initialized = self.client.request('initialize', {
            'processId': None, 'rootUri': self.dir.as_uri(), 'capabilities': {}})
        self.capabilities = initialized['result']['capabilities']
        self.client.notify('initialized')

    def tearDown(self):
        if self.client.process.poll() is None:
            reply = self.client.request('shutdown')
            self.assertIsNone(reply['result'])
            self.client.notify('exit')
            self.assertEqual(self.client.process.wait(timeout=30), 0)

    def open(self, name, text, version=1):
        path = self.dir / name
        path.write_text(text, encoding='utf-8')
        uri = path.as_uri()
        self.client.notify('textDocument/didOpen', {'textDocument': {
            'uri': uri, 'languageId': 'python', 'version': version, 'text': text}})
        return path, uri

    def test_capabilities(self):
        sync = self.capabilities['textDocumentSync']
        self.assertTrue(sync['openClose'])
        self.assertEqual(sync['change'], 1)
        self.assertTrue(sync['save'])

    def test_clean_file_publishes_an_empty_list(self):
        _, uri = self.open('clean.py', CLEAN)
        self.assertEqual(self.client.diagnostics(uri), [])

    def test_refusal_is_an_error_at_its_line(self):
        _, uri = self.open('refusal.py', REFUSAL)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item['severity'], 1)
        self.assertEqual(item['source'], 'ail')
        self.assertEqual(item['range']['start']['line'], 2)
        self.assertIn('second name for the same container', item['message'])

    def test_change_is_debounced_and_save_and_close_republish(self):
        path, uri = self.open('change.py', CLEAN)
        self.assertEqual(self.client.diagnostics(uri), [])
        self.client.notify('textDocument/didChange', {
            'textDocument': {'uri': uri, 'version': 2},
            'contentChanges': [{'text': REFUSAL}]})
        (item,) = self.client.diagnostics(uri, version=2)
        self.assertEqual(item['range']['start']['line'], 2)
        path.write_text(CLEAN, encoding='utf-8')
        self.client.notify('textDocument/didSave', {'textDocument': {'uri': uri}, 'text': CLEAN})
        self.assertEqual(self.client.diagnostics(uri, version=2, expected=[]), [])
        self.client.notify('textDocument/didClose', {'textDocument': {'uri': uri}})
        self.assertEqual(self.client.diagnostics(uri), [])

    def test_unknown_request_and_exit_status(self):
        reply = self.client.request('textDocument/definition', {})
        self.assertEqual(reply['error']['code'], -32601)
        self.assertIsNone(self.client.request('shutdown')['result'])
        self.client.notify('exit')
        self.assertEqual(self.client.process.wait(timeout=30), 0)


if __name__ == '__main__':
    unittest.main()
