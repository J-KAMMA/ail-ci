"""`ail lsp` go-to-definition: a scripted session over the probe files in lab/lsp/def/.

Every position in `lab/lsp/def/expect.json` is checked against `textDocument/definition`. The probe
covers a local with one binding and with two, parameters, globals, `global`/`nonlocal`, functions,
classes, `self.m()`, `from helper import pick`, `import helper` then `helper.pick`, a module beside
the program, a module on AIL_PATH and a bundled stdlib module, a comprehension variable (including
its iterable, which runs in the enclosing scope), a plain `import pkg.sub` binding the package, UTF-16
positions after an astral character, `except ... as name` and `match` captures, and the places that
must stay empty (a string, a comment, an unknown attribute, a builtin).
"""
import json
import os
import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / "packaging"
PROBES = ROOT.parent / "lab" / "lsp" / "def"
EXPECT = PROBES / "expect.json"


def setUpModule():
    if not (PACKAGING / "ail_lang" / "lsp.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")
    if not EXPECT.is_file():
        raise unittest.SkipTest("lab/lsp/def/expect.json is not beside AIL_CURRENT")


class Client:
    def __init__(self, cwd):
        env = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT), PYTHONUTF8="1",
                   AIL_PATH=str(PROBES / "lib"))
        self.process = subprocess.Popen([sys.executable, "-B", "-m", "ail_lang", "lsp"], cwd=str(cwd),
                                        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
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

    def open(self, path, text=None):
        if text is None:
            text = path.read_text(encoding="utf-8")
        self.notify("textDocument/didOpen", {"textDocument": {"uri": path.as_uri(), "languageId": "python",
                                                              "version": 1, "text": text}})

    def definition(self, path, line, character):
        reply = self.request("textDocument/definition", {
            "textDocument": {"uri": path.as_uri()},
            "position": {"line": line, "character": character}})
        return reply.get("result")

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


def expected_locations(target):
    if target is None:
        return None
    items = target if isinstance(target, list) else [target]
    found = []
    for item in items:
        if "module" in item:
            found.append((str((PROBES / item["module"]).resolve()), 0, 0, 0, 0))
        elif "bundled" in item:
            found.append((str((ROOT / "stdlib" / item["bundled"]).resolve()), 0, 0, 0, 0))
        else:
            found.append((str((PROBES / item["file"]).resolve()), item["line"], item["character"],
                          item["line"], item["end_character"]))
    return sorted(found)


def actual_locations(result):
    if not result:
        return None
    found = []
    for location in result:
        from urllib.parse import unquote, urlparse
        from urllib.request import url2pathname
        parsed = urlparse(location["uri"])
        path = str(Path(url2pathname(unquote(parsed.path))).resolve())
        start, end = location["range"]["start"], location["range"]["end"]
        found.append((path, start["line"], start["character"], end["line"], end["character"]))
    return sorted(found)


class Definition(unittest.TestCase):
    def setUp(self):
        self.client = Client(PROBES)
        self.addCleanup(self.client.close)
        initialized = self.client.request("initialize", {"processId": None, "rootUri": PROBES.as_uri(),
                                                         "capabilities": {}})
        self.capabilities = initialized["result"]["capabilities"]
        self.client.notify("initialized")
        self.data = json.loads(EXPECT.read_text(encoding="utf-8"))
        self.files = {name: PROBES / name for name in self.data["files"]}
        for path in self.files.values():
            self.client.open(path)

    def test_advertises_definition(self):
        self.assertTrue(self.capabilities["definitionProvider"])

    def test_every_position_in_the_probe(self):
        wrong = []
        for index, case in enumerate(self.data["cases"], 1):
            path = self.files[case["file"]]
            result = self.client.definition(path, case["line"], case["character"])
            want = expected_locations(case["target"])
            got = actual_locations(result)
            if got != want:
                worst = "wrong" if got is not None else "none"
                wrong.append("#%d %s:%d:%d want %s got %s (%s)"
                             % (index, case["file"], case["line"], case["character"], want, got, worst))
        self.assertEqual(wrong, [])

    def test_uses_the_open_buffer_of_an_imported_module(self):
        shifted = "\n\n" + (PROBES / "helper.py").read_text(encoding="utf-8")
        self.client.open(PROBES / "helper.py", shifted)
        result = self.client.definition(PROBES / "main.py", 40, 11)     # pick(local, local)
        want = [(str((PROBES / "helper.py").resolve()), 7, 4, 7, 8)]
        self.assertEqual(actual_locations(result), want)


class ServerProtocol(unittest.TestCase):
    def test_a_malformed_definition_request_is_method_not_found(self):
        client = Client(PROBES)
        self.addCleanup(client.close)
        client.request("initialize", {"processId": None, "rootUri": PROBES.as_uri(), "capabilities": {}})
        reply = client.request("textDocument/definition", {})
        self.assertEqual(reply["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
