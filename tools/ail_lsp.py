#!/usr/bin/env python3
"""A diagnostics-only Language Server Protocol server for AIL over stdio.

The compiler's ``check`` command is the authority: every open, change (debounced)
and save writes the document to a temporary file and runs

    python3 AIL_CURRENT/ail_chatgpt.py check <file> --syntax python

The user's program is never built or executed.  Each refusal or error becomes an
LSP Diagnostic with severity Error and source ``ail``; a clean check publishes an
empty list.
"""
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
DEBOUNCE = 0.5
CHECK_TIMEOUT = 300
ERROR = 1



def _frames(buffer):
    """Pop complete Content-Length framed JSON messages from a byte buffer."""
    messages = []
    while True:
        end = buffer.find(b'\r\n\r\n')
        separator = 4
        if end < 0:
            end = buffer.find(b'\n\n')
            separator = 2
        if end < 0:
            return messages
        length = None
        for line in bytes(buffer[:end]).splitlines():
            name, _, value = line.partition(b':')
            if name.strip().lower() == b'content-length':
                try:
                    length = int(value.strip())
                except ValueError:
                    length = None
        if length is None or len(buffer) < end + separator + length:
            return messages
        body = bytes(buffer[end + separator:end + separator + length])
        del buffer[:end + separator + length]
        try:
            messages.append(json.loads(body.decode('utf-8')))
        except (UnicodeError, json.JSONDecodeError):
            pass


def _path_from_uri(uri):
    parsed = urlparse(uri)
    if parsed.scheme == 'file':
        return Path(unquote(parsed.path))
    return Path(unquote(uri))


def _clean_message(message):
    text = str(message).strip()
    text = re.sub(r'^AIL (?:source|module) .*?: (?:line \d+: )?', '', text)
    text = re.sub(r'^line \d+: ', '', text)
    text = re.sub(r'^.*?:\d+:\d+: ', '', text, count=1)
    return text.strip()


def _message_position(message):
    """Recover a line/column from the compiler's own message text."""
    line = column = None
    match = re.search(r'\bline\s+(\d+)', message)
    if match:
        line = int(match.group(1))
    match = re.search(r'\bcolumn\s+(\d+)', message)
    if match:
        column = int(match.group(1))
    if column is None:
        match = re.search(r':(\d+):(\d+):', message)
        if match:
            line = int(match.group(1))
            column = int(match.group(2))
    return line, column


class Server:
    def __init__(self, out):
        self.out = out
        self.documents = {}
        self.pending = {}
        self.shutdown_requested = False
        self.exit_code = None
        self.temp = Path(tempfile.mkdtemp(prefix='ail-lsp-'))
        self._counter = 0

    def close(self):
        for doc in self.documents.values():
            path = doc.get('path')
            if path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass
        self.documents.clear()
        shutil.rmtree(self.temp, ignore_errors=True)

    def send(self, message):
        payload = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.out.write(b'Content-Length: %d\r\n\r\n' % len(payload))
        self.out.write(payload)
        self.out.flush()

    def reply(self, identifier, result=None, error=None):
        message = {'jsonrpc': '2.0', 'id': identifier}
        if error is None:
            message['result'] = result
        else:
            message['error'] = error
        self.send(message)

    def publish(self, uri, diagnostics, version=None):
        params = {'uri': uri, 'diagnostics': diagnostics}
        if version is not None:
            params['version'] = version
        self.send({'jsonrpc': '2.0', 'method': 'textDocument/publishDiagnostics', 'params': params})

    def handle(self, message):
        method = message.get('method')
        identifier = message.get('id')
        params = message.get('params') or {}
        if method == 'initialize':
            self.reply(identifier, {'capabilities': {
                'textDocumentSync': {'openClose': True, 'change': 1, 'save': True},
            }})
        elif method == 'initialized':
            pass
        elif method == 'shutdown':
            self.shutdown_requested = True
            self.reply(identifier, None)
        elif method == 'exit':
            self.exit_code = 0 if self.shutdown_requested else 1
        elif method == 'textDocument/didOpen':
            self.did_open(params)
        elif method == 'textDocument/didChange':
            self.did_change(params)
        elif method == 'textDocument/didSave':
            self.did_save(params)
        elif method == 'textDocument/didClose':
            self.did_close(params)
        elif identifier is not None:
            self.reply(identifier, error={'code': -32601, 'message': 'method not found: %s' % method})

    def did_open(self, params):
        document = params.get('textDocument') or {}
        uri = document.get('uri')
        if not uri:
            return
        self.documents[uri] = {'text': document.get('text') or '', 'version': document.get('version', 1),
                               'path': None}
        self.check_and_publish(uri)

    def did_change(self, params):
        document = params.get('textDocument') or {}
        uri = document.get('uri')
        doc = self.documents.get(uri)
        if doc is None:
            return
        changes = params.get('contentChanges') or []
        if changes:
            doc['text'] = changes[-1].get('text') or ''
        doc['version'] = document.get('version', doc['version'] + 1)
        self.pending[uri] = (time.monotonic() + DEBOUNCE, doc['version'])

    def did_save(self, params):
        document = params.get('textDocument') or {}
        uri = document.get('uri')
        doc = self.documents.get(uri)
        if doc is None:
            return
        text = params.get('text')
        if text is not None:
            doc['text'] = text
        self.pending.pop(uri, None)
        self.check_and_publish(uri)

    def did_close(self, params):
        document = params.get('textDocument') or {}
        uri = document.get('uri')
        self.pending.pop(uri, None)
        doc = self.documents.pop(uri, None)
        if doc is not None and doc.get('path') is not None:
            try:
                doc['path'].unlink()
            except OSError:
                pass
        self.publish(uri, [])

    def flush_pending(self):
        now = time.monotonic()
        for uri, (deadline, version) in list(self.pending.items()):
            if deadline > now:
                continue
            del self.pending[uri]
            doc = self.documents.get(uri)
            if doc is not None and doc.get('version') == version:
                self.check_and_publish(uri)

    def document_path(self, uri, doc):
        if doc.get('path') is None:
            self._counter += 1
            source = _path_from_uri(uri)
            # The compiler resolves sibling imports from the entry file's directory, so the
            # temporary copy must live beside the document.  Fall back to the private directory
            # only when there is no writable document directory (an untitled buffer, say).
            directory = source.parent if source.is_absolute() and source.parent.is_dir() else self.temp
            prefix = '.ail-lsp-%d-%d-' % (os.getpid(), self._counter)
            try:
                handle, name = tempfile.mkstemp(prefix=prefix, suffix='.py', dir=str(directory))
            except OSError:
                handle, name = tempfile.mkstemp(prefix=prefix, suffix='.py', dir=str(self.temp))
            os.close(handle)
            doc['path'] = Path(name)
        return doc['path']

    def check_and_publish(self, uri):
        doc = self.documents.get(uri)
        if doc is None:
            return
        path = self.document_path(uri, doc)
        try:
            path.write_text(doc['text'], encoding='utf-8')
        except OSError as error:
            self.publish(uri, [self._diagnostic(1, 1, 'cannot write the document: %s' % error)],
                         doc.get('version'))
            return
        diagnostics = self.check(path)
        self.publish(uri, diagnostics, doc.get('version'))

    def check(self, path):
        env = dict(os.environ)
        env['PYTHONUTF8'] = '1'
        env.pop('AIL_SURFACE', None)
        try:
            process = subprocess.run(
                [sys.executable, '-B', str(COMPILER), 'check', str(path), '--syntax', 'python'],
                cwd=str(ROOT), capture_output=True, text=True, timeout=CHECK_TIMEOUT, env=env)
        except (OSError, subprocess.SubprocessError) as error:
            return [self._diagnostic(1, 1, 'cannot run the AIL check: %s' % error)]
        return self.parse(process, path)

    def parse(self, process, path):
        report = None
        if process.stdout.strip():
            try:
                report = json.loads(process.stdout)
            except json.JSONDecodeError:
                report = None
        if isinstance(report, dict):
            if report.get('status') == 'passed':
                return []
            diagnostics = [self._diagnostic_from_item(item) for item in (report.get('diagnostics') or [])]
            if diagnostics:
                return diagnostics
        return self._parse_text(process)

    def _parse_text(self, process):
        text = (process.stderr or '') + '\n' + (process.stdout or '')
        diagnostics = []
        for line in text.splitlines():
            match = re.match(r'^(.*?):(\d+):(\d+):\s*(.*)$', line)
            if match:
                diagnostics.append(self._diagnostic(int(match.group(2)), int(match.group(3)), match.group(4)))
                continue
            match = re.match(r'^(.*?):(\d+):\s*(.*)$', line)
            if match:
                diagnostics.append(self._diagnostic(int(match.group(2)), 1, match.group(3)))
        if diagnostics:
            return diagnostics
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or 'AIL check failed').strip()
            return [self._diagnostic(1, 1, detail.splitlines()[-1] if detail else 'AIL check failed')]
        return []

    def _diagnostic_from_item(self, item):
        message = str(item.get('message') or '')
        line = item.get('line')
        column = item.get('column')
        if line is None:
            found_line, found_column = _message_position(message)
            line = found_line if found_line is not None else 1
            if column is None:
                column = found_column if found_column is not None else 1
        if column is None:
            column = 1
        return self._diagnostic(int(line), int(column), _clean_message(message))

    def _diagnostic(self, line, column, message):
        line = max(1, int(line))
        column = max(1, int(column))
        return {
            'range': {
                'start': {'line': line - 1, 'character': column - 1},
                'end': {'line': line - 1, 'character': column},
            },
            'severity': ERROR,
            'source': 'ail',
            'message': message or 'AIL check failed',
        }


def main():
    server = Server(sys.stdout.buffer)
    selector = selectors.DefaultSelector()
    stream = sys.stdin.buffer
    selector.register(stream, selectors.EVENT_READ)
    buffer = bytearray()
    try:
        while server.exit_code is None:
            timeout = None
            if server.pending:
                timeout = max(0.0, min(deadline for deadline, _ in server.pending.values()) - time.monotonic())
            if selector.select(timeout):
                data = os.read(stream.fileno(), 65536)
                if not data:
                    break
                buffer.extend(data)
                for message in _frames(buffer):
                    server.handle(message)
                    if server.exit_code is not None:
                        break
            server.flush_pending()
    finally:
        selector.close()
        server.close()
    return server.exit_code if server.exit_code is not None else 1


if __name__ == '__main__':
    raise SystemExit(main())
