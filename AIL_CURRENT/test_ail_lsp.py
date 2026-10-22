"""`ail lsp` (packaging/ail_lang/lsp.py): the language server over stdio, driven by a scripted LSP client.

* initialize advertises open/close sync, save notifications and hover;
* didOpen / didSave publish diagnostics from `ail check`: a source that does not load is an Error with its
  "write instead:" text; a typed-path blocker the general path builds is a Warning "runs on the slow general
  path because ..."; `strict = true` in ail.toml makes the blocker an Error; a clean file publishes none;
* hover on a diagnostic shows the rewrite;
* didClose clears, unknown requests get -32601, shutdown + exit end the process with status 0.

The warning/error split builds the program once, so those cases need a C compiler and are skipped without one.
The tests are skipped when the repository's packaging/ directory is not beside this directory (an SDK export).
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
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

CLEAN = "def main() -> None:\n    print(1 + 2)\n\n\nmain()\n"
# the typed path refuses `int | None`; the general path builds it
BLOCKER = ("def find(d: dict[int, int], k: int) -> int | None:\n    return d.get(k)\n\n\n"
           "def main() -> None:\n    print(find({1: 2}, 1))\n\n\nmain()\n")
# refused outright: main() is never called
REFUSED = "def main() -> None:\n    print('hi')\n"
BROKEN = "def main() -> None:\n    x = [1, 2\n    print(x)\nmain()\n"


def setUpModule():
    if not (PACKAGING / "ail_lang" / "lsp.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")


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
        return self.until(lambda m: m.get("id") == identifier)

    def notify(self, method, params=None):
        self.send({"method": method, "params": params or {}})

    def until(self, predicate, timeout=300):
        while True:
            message = self.messages.get(timeout=timeout)
            if message is None:
                raise AssertionError("the server closed its output")
            if predicate(message):
                return message

    def diagnostics(self, uri):
        message = self.until(lambda m: m.get("method") == "textDocument/publishDiagnostics"
                             and m["params"]["uri"] == uri)
        return message["params"]["diagnostics"]

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


class LspCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-lsp-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.client = Client(self.dir)
        self.addCleanup(self.client.close)
        initialized = self.client.request("initialize", {"processId": None, "rootUri": self.dir.as_uri(),
                                                         "capabilities": {}})
        self.capabilities = initialized["result"]["capabilities"]
        self.client.notify("initialized")

    def write(self, name, text):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path, path.as_uri()

    def open(self, name, text):
        path, uri = self.write(name, text)
        self.client.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "python",
                                                                      "version": 1, "text": text}})
        return path, uri


class Protocol(LspCase):
    def test_capabilities(self):
        sync = self.capabilities["textDocumentSync"]
        self.assertTrue(sync["openClose"])
        self.assertTrue(sync["save"])
        self.assertTrue(self.capabilities["hoverProvider"])

    def test_clean_file_publishes_an_empty_list(self):
        _, uri = self.open("clean.py", CLEAN)
        self.assertEqual(self.client.diagnostics(uri), [])

    def test_unknown_request_is_an_error_and_shutdown_exits_zero(self):
        reply = self.client.request("textDocument/definition", {})
        self.assertEqual(reply["error"]["code"], -32601)
        self.assertIsNone(self.client.request("shutdown")["result"])
        self.client.notify("exit")
        self.assertEqual(self.client.process.wait(timeout=30), 0)

    def test_exit_without_shutdown_is_status_one(self):
        self.client.notify("exit")
        self.assertEqual(self.client.process.wait(timeout=30), 1)

    def test_a_syntax_error_is_an_error_at_its_line(self):
        _, uri = self.open("broken.py", BROKEN)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 1)
        self.assertEqual(item["source"], "ail")
        self.assertEqual(item["range"]["start"]["line"], 1)
        self.assertIn("never closed", item["message"])

    def test_a_refusal_is_an_error_with_the_rewrite_and_hover_shows_it(self):
        _, uri = self.open("refused.py", REFUSED)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 1)
        self.assertIn("write instead:", item["message"])
        position = item["range"]["start"]
        hover = self.client.request("textDocument/hover", {"textDocument": {"uri": uri}, "position": position})
        text = hover["result"]["contents"]["value"]
        self.assertIn("**write instead:**", text)
        self.assertIn("add `main()` as the last line", text)
        far = self.client.request("textDocument/hover", {"textDocument": {"uri": uri},
                                                         "position": {"line": 40, "character": 0}})
        self.assertIsNone(far["result"])

    def test_save_republishes_and_close_clears(self):
        path, uri = self.open("edit.py", BROKEN)
        self.assertEqual(self.client.diagnostics(uri)[0]["severity"], 1)
        path.write_text(CLEAN, encoding="utf-8")
        self.client.notify("textDocument/didSave", {"textDocument": {"uri": uri}})
        self.assertEqual(self.client.diagnostics(uri), [])
        path.write_text(BROKEN, encoding="utf-8")
        self.client.notify("textDocument/didSave", {"textDocument": {"uri": uri}})
        self.assertEqual(len(self.client.diagnostics(uri)), 1)
        self.client.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
        self.assertEqual(self.client.diagnostics(uri), [])

    def test_an_unsaved_new_file_is_checked_from_the_buffer(self):
        uri = (self.dir / "never_saved.py").as_uri()
        self.client.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "python",
                                                                      "version": 1, "text": BROKEN}})
        self.assertEqual(self.client.diagnostics(uri)[0]["severity"], 1)
        self.assertFalse((self.dir / "never_saved.py").exists())


@unittest.skipUnless(CC, "the warning/error split builds the program once: no C compiler")
class GeneralPath(LspCase):
    def test_a_blocker_the_general_path_builds_is_a_warning(self):
        _, uri = self.open("blocker.py", BLOCKER)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 2)
        self.assertTrue(item["message"].startswith("runs on the slow general path because "), item["message"])
        self.assertIn("int | None", item["message"])
        self.assertIn("write instead:", item["message"])
        hover = self.client.request("textDocument/hover", {
            "textDocument": {"uri": uri}, "position": item["range"]["start"]})
        self.assertIn("**write instead:** return a sentinel", hover["result"]["contents"]["value"])

    def test_strict_project_makes_the_blocker_an_error(self):
        (self.dir / "ail.toml").write_text('entry = "blocker.py"\nstrict = true\n', encoding="utf-8")
        _, uri = self.open("blocker.py", BLOCKER)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 1)
        self.assertNotIn("slow general path", item["message"])
        self.assertIn("write instead:", item["message"])


class Classify(unittest.TestCase):
    """The Warning / Error rule, without a build."""

    def diagnoser(self, verdict):
        sys.path.insert(0, str(PACKAGING))
        self.addCleanup(sys.path.remove, str(PACKAGING))
        from ail_lang import lsp
        diagnoser = lsp.Diagnoser()
        diagnoser.builds_on_general_path = lambda *args, **kwargs: verdict
        return lsp, diagnoser

    ITEM = {"code": "type", "message": "dunder method A.__getattr__; only __init__ is supported", "path": "/x/a.py",
            "line": 5, "column": 3}
    REPORT = {"stage": "type", "source_sha256": "0" * 64}

    def test_general_path_builds_it_is_a_warning(self):
        lsp, diagnoser = self.diagnoser(True)
        problem = diagnoser.classify(Path("/x/a.py"), self.ITEM, self.REPORT, [], False)
        self.assertEqual(problem[3], lsp.WARNING)
        self.assertTrue(problem[5].startswith("runs on the slow general path because dunder method"))

    def test_refused_by_the_build_is_an_error_with_the_checker_message(self):
        lsp, diagnoser = self.diagnoser(False)
        problem = diagnoser.classify(Path("/x/a.py"), self.ITEM, self.REPORT, [], False)
        self.assertEqual((problem[3], problem[5]), (lsp.ERROR, self.ITEM["message"]))

    def test_strict_and_loader_failures_are_errors_without_a_build(self):
        lsp, diagnoser = self.diagnoser("must not be asked")
        self.assertEqual(diagnoser.classify(Path("/x/a.py"), self.ITEM, self.REPORT, [], True)[3], lsp.ERROR)
        loader = dict(self.REPORT, stage="loader")
        self.assertEqual(diagnoser.classify(Path("/x/a.py"), self.ITEM, loader, [], False)[3], lsp.ERROR)

    def test_no_compiler_is_a_warning_that_says_so(self):
        lsp, diagnoser = self.diagnoser(None)
        problem = diagnoser.classify(Path("/x/a.py"), self.ITEM, self.REPORT, [], False)
        self.assertEqual(problem[3], lsp.WARNING)
        self.assertIn("no C compiler", problem[5])

    def test_rewrite_text_and_ranges(self):
        lsp, _ = self.diagnoser(True)
        self.assertEqual(lsp.rewrite_of("no.\n  write instead: use `x`\n"), "use `x`")
        self.assertIsNone(lsp.rewrite_of("nothing to write"))


if __name__ == "__main__":
    unittest.main()
