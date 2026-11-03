"""`ail lsp` (packaging/ail_lang/lsp.py): the language server over stdio, driven by a scripted LSP client.

* initialize advertises open/close sync, didChange, save notifications and hover;
* didOpen / didChange / didSave publish diagnostics from `ail check`: a source that does not load is an Error
  with its "write instead:" text; a typed-path blocker the general path builds is a Warning "runs on the slow
  general path because ..."; `strict = true` in ail.toml makes it an Error; a clean file publishes none;
* hover on a diagnostic shows the rewrite, and elsewhere a certain annotation, literal type or signature;
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
# a real front-end type error: the annotation and the value disagree
TYPE_ERROR = 'def main() -> None:\n    x: int = "hi"\n    print(x)\n\n\nmain()\n'
TYPED = ("def total() -> int:\n    value: int = 3\n    return value\n\n\n"
         "def main() -> None:\n    print(total())\n\n\nmain()\n")
LITERALS = ("def main() -> None:\n    i = 1\n    f = 2.5\n    s = 'text'\n    b = b'raw'\n"
            "    t = True\n    n = None\n    print(i, f, s, b, t, n)\n\n\nmain()\n")
PROBE = ("def main() -> None:\n    a = 1 / 2\n    b = not 1\n    c = abs(-3.5)\n"
         "    d = sum([1.5, 2.5])\n    n = round(1.234, 2)\n    print(a, b, c, d, n)\n\n\nmain()\n")
MIXED = ("def main() -> None:\n    m = 1\n    m = 2.5\n    print(m)\n\n\nmain()\n")
CALLS = ("def main() -> None:\n    raw = b'a b'.split()\n    rng = range(3)\n"
         "    print(raw, rng)\n\n\nmain()\n")
STRINGS = ("def main() -> None:\n    x = 1\n    print('x = 2')  # x = 3\n\n\nmain()\n")


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

    def test_a_buffer_diagnostic_never_shows_the_temp_file_name(self):
        _, uri = self.open("helper.py", BROKEN)
        (item,) = self.client.diagnostics(uri)
        self.assertNotIn(".ail-lsp-", item["message"])
        self.assertIn("helper.py", item["message"])

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory modes")
    def test_a_read_only_directory_publishes_a_syntax_error(self):
        folder = self.dir / "readonly"
        folder.mkdir()
        folder.chmod(0o555)
        self.addCleanup(folder.chmod, 0o755)
        uri = (folder / "broken.py").as_uri()
        self.client.notify("textDocument/didOpen", {
            "textDocument": {"uri": uri, "languageId": "python", "version": 1, "text": BROKEN}})
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 1)
        self.assertIn("never closed", item["message"])
        self.assertNotIn(".ail-lsp-", item["message"])

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory modes")
    def test_a_read_only_directory_still_resolves_imports(self):
        folder = self.dir / "readonly-import"
        folder.mkdir()
        (folder / "dep.py").write_text("def value() -> int:\n    return 7\n", encoding="utf-8")
        folder.chmod(0o555)
        self.addCleanup(folder.chmod, 0o755)
        text = "from dep import value\n\ndef main() -> None:\n    print(value())\n\n\nmain()\n"
        uri = (folder / "main.py").as_uri()
        self.client.notify("textDocument/didOpen", {
            "textDocument": {"uri": uri, "languageId": "python", "version": 1, "text": text}})
        self.assertEqual(self.client.diagnostics(uri), [])

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

    def test_did_change_rechecks_the_buffer_without_writing_the_file(self):
        path, uri = self.open("change.py", CLEAN)
        self.assertEqual(self.client.diagnostics(uri), [])
        self.client.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": 2},
            "contentChanges": [{"text": BROKEN}]})
        self.assertEqual(self.client.diagnostics(uri)[0]["severity"], 1)
        self.assertEqual(path.read_text(encoding="utf-8"), CLEAN)
        self.client.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": 3},
            "contentChanges": [{"text": CLEAN}]})
        self.assertEqual(self.client.diagnostics(uri), [])

    def test_an_incremental_did_change_uses_its_range(self):
        path, uri = self.open("incremental.py", CLEAN)
        self.assertEqual(self.client.diagnostics(uri), [])
        self.client.notify("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": 2},
            "contentChanges": [{"range": {"start": {"line": 1, "character": 10},
                                          "end": {"line": 1, "character": 15}}, "text": "1 +"}]})
        self.assertEqual(len(self.client.diagnostics(uri)), 1)
        self.assertEqual(path.read_text(encoding="utf-8"), CLEAN)

    def test_hover_shows_an_annotation_and_a_signature(self):
        _, uri = self.open("types.py", TYPED)
        self.assertEqual(self.client.diagnostics(uri), [])
        annotated = self.client.request("textDocument/hover", {
            "textDocument": {"uri": uri}, "position": {"line": 1, "character": 5}})
        self.assertIn("`value`: `int`", annotated["result"]["contents"]["value"])
        signature = self.client.request("textDocument/hover", {
            "textDocument": {"uri": uri}, "position": {"line": 0, "character": 4}})
        self.assertIn("def total() -> int", signature["result"]["contents"]["value"])

    def test_hover_shows_a_type_only_for_literal_assignments(self):
        _, uri = self.open("literals.py", LITERALS)
        expected = [("i", 1, "int"), ("f", 2, "float"), ("s", 3, "str"),
                    ("b", 4, "bytes"), ("t", 5, "bool"), ("n", 6, "None")]
        for name, line, kind in expected:
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": uri}, "position": {"line": line, "character": 4}})
            self.assertEqual(answer["result"]["contents"]["value"], "`%s`: `%s`" % (name, kind))

    def test_hover_is_none_for_the_review_probe_and_derived_names(self):
        _, uri = self.open("probe.py", PROBE)
        self.assertEqual(self.client.diagnostics(uri), [])
        for line in range(1, 6):
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": uri}, "position": {"line": line, "character": 4}})
            self.assertIsNone(answer["result"], "line %d" % line)

    def test_hover_is_none_for_a_mixed_type_and_for_calls(self):
        _, mixed = self.open("mixed.py", MIXED)
        for line in (1, 2):
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": mixed}, "position": {"line": line, "character": 4}})
            self.assertIsNone(answer["result"])
        _, calls = self.open("calls.py", CALLS)
        for line, character in ((1, 4), (2, 4), (1, 17), (2, 10)):
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": calls}, "position": {"line": line, "character": character}})
            self.assertIsNone(answer["result"])

    def test_hover_ignores_strings_and_comments(self):
        _, uri = self.open("strings.py", STRINGS)
        self.assertEqual(self.client.diagnostics(uri), [])
        name = self.client.request("textDocument/hover", {
            "textDocument": {"uri": uri}, "position": {"line": 1, "character": 4}})
        self.assertIn("`x`: `int`", name["result"]["contents"]["value"])
        for character in (11, 22):
            answer = self.client.request("textDocument/hover", {
                "textDocument": {"uri": uri}, "position": {"line": 2, "character": character}})
            self.assertIsNone(answer["result"])

    def test_a_type_error_in_a_strict_project_is_an_error(self):
        (self.dir / "strict").mkdir()
        (self.dir / "strict" / "ail.toml").write_text('entry = "type_error.py"\nstrict = true\n', encoding="utf-8")
        _, uri = self.open("strict/type_error.py", TYPE_ERROR)
        (item,) = self.client.diagnostics(uri)
        self.assertEqual(item["severity"], 1)
        self.assertEqual(item["range"]["start"]["line"], 1)
        self.assertIn("declared int", item["message"])

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


    def test_scripted_session_on_clean_type_error_and_fallback_files(self):
        _, clean = self.open("clean.py", CLEAN)
        self.assertEqual(self.client.diagnostics(clean), [])
        (self.dir / "strict").mkdir()
        (self.dir / "strict" / "ail.toml").write_text('entry = "type_error.py"\nstrict = true\n', encoding="utf-8")
        _, type_error = self.open("strict/type_error.py", TYPE_ERROR)
        self.assertEqual(self.client.diagnostics(type_error)[0]["severity"], 1)
        _, fallback = self.open("blocker.py", BLOCKER)
        (item,) = self.client.diagnostics(fallback)
        self.assertEqual(item["severity"], 2)
        self.assertTrue(item["message"].startswith("runs on the slow general path because "), item["message"])
        self.assertIn("int | None", item["message"])


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
