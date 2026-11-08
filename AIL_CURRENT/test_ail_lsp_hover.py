"""`ail lsp` hover with compiler-inferred types: the 35-name probe in lab/lsp/hover/.

Every case in `lab/lsp/hover/expect.json` is checked against `textDocument/hover`: a case with an
`expected` type must show that type, and a case with `expected: null` must show nothing. The
`oracle` field is the `type(x).__name__` CPython prints at that line (see `oracle.py`). The compiler
part needs a C compiler; without one the test is skipped.
"""
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / "packaging"
PROBES = ROOT.parent / "lab" / "lsp" / "hover"
EXPECT = PROBES / "expect.json"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def setUpModule():
    if not (PACKAGING / "ail_lang" / "lsp.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")
    if not EXPECT.is_file():
        raise unittest.SkipTest("lab/lsp/hover/expect.json is not beside AIL_CURRENT")


class Client:
    def __init__(self, cwd):
        env = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1")
        self.process = subprocess.Popen([sys.executable, "-B", "-m", "ail_lang", "lsp"], cwd=cwd, env=env,
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
                name, _, value = line.decode("ascii").partition(":")
                if name.lower() == "content-length":
                    length = int(value)
            self.messages.put(json.loads(stream.read(length).decode("utf-8")))

    def send(self, message):
        data = json.dumps(dict(jsonrpc="2.0", **message)).encode("utf-8")
        self.process.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        self.process.stdin.flush()

    def request(self, method, params=None):
        identifier, self.next_id = self.next_id, self.next_id + 1
        self.send({"id": identifier, "method": method, "params": params or {}})
        return self.until(lambda message: message.get("id") == identifier)

    def notify(self, method, params=None):
        self.send({"method": method, "params": params or {}})

    def until(self, predicate, timeout=300):
        while True:
            message = self.messages.get(timeout=timeout)
            if message is None:
                raise AssertionError("the server closed its output")
            if predicate(message):
                return message

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


@unittest.skipUnless(CC, "the compiler-inferred types need a C compiler")
class HoverProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-lsp-hover-")
        self.addCleanup(self.tmp.cleanup)
        self.client = Client(self.tmp.name)
        self.addCleanup(self.client.close)
        self.client.request("initialize", {"processId": None, "rootUri": Path(self.tmp.name).as_uri(),
                                           "capabilities": {}})
        self.client.notify("initialized")

    def open_saved(self, name):
        text = (PROBES / name).read_text(encoding="utf-8")
        uri = (PROBES / name).as_uri()
        self.client.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "python", "version": 1, "text": text}})
        self.client.notify("textDocument/didSave", {"textDocument": {"uri": uri}})
        return uri

    def test_all_35_cases(self):
        expect = json.loads(EXPECT.read_text(encoding="utf-8"))
        uris = {name: self.open_saved(name) for name in expect["files"]}
        for case in expect["cases"]:
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": uris[case["file"]]},
                "position": {"line": case["line"], "character": case["character"]}})
            expected = case["expected"]
            if expected is None:
                self.assertIsNone(answer["result"], "%s:%d %s must show nothing"
                                  % (case["file"], case["line"] + 1, case["name"]))
            else:
                value = answer["result"]["contents"]["value"]
                self.assertIn("`%s`: `%s`" % (case["name"], expected), value,
                              "%s:%d %s" % (case["file"], case["line"] + 1, case["name"]))


if __name__ == "__main__":
    unittest.main()
