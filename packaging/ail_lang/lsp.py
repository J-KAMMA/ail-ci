"""`ail lsp`: a small language server over stdio (JSON-RPC, Content-Length framing). Standard library only.

* Diagnostics on didOpen and didSave, from `ail check` (schema ail.check/1). A source that does not parse or
  load is an Error. A program the typed path refuses is built anyway on the slow general path, and the
  server tells the two apart by building it once (a C compiler is needed for that; the result is cached
  per source hash):
    - the build works         Warning "runs on the slow general path because <reason>"
    - the build is refused    Error   "<refusal>" (both carry the compiler's "write instead:" text)
  With `strict = true` in the project (ail.toml / [tool.ail]) every typed-path refusal is an Error.
  `slow_patterns` of the report (quadratic shapes) are Information.
* Hover on a diagnostic shows the rewrite ("write instead: ...") or, when there is none, the message.
* The file on disk is checked, so diagnostics follow the last save; didChange is not requested.
The blocker list comes from `compile --strict --json` (ail.strict/1: every blocker, with its rewrite); `classify()` decides
Warning or Error.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from . import cli, project

ERROR, WARNING, INFORMATION = 1, 2, 3
HARD_CODES = ("syntax", "io", "configuration", "dependency")      # never a general-path fallback
WRITE_INSTEAD = re.compile(r"write instead:\s*(.+)", re.S)
SLOW_PATTERN = re.compile(r"^(?P<path>.*?):(?P<line>\d+): slow: (?P<text>.*)$")
CHECK_TIMEOUT = 120
BUILD_TIMEOUT = 300


def uri_to_path(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = url2pathname(unquote(parsed.path))
    if os.name == "nt" and re.match(r"^[\\/][A-Za-z]:", path):
        path = path[1:]
    return Path(path)


def path_to_uri(path):
    return Path(path).resolve().as_uri()


def rewrite_of(message):
    """The text after `write instead:`, or None."""
    found = WRITE_INSTEAD.search(message or "")
    return found.group(1).strip() if found else None


class Diagnoser:
    """Runs `ail check` (and, to classify a refusal, one build) and turns the result into LSP diagnostics."""

    def __init__(self):
        self.verdicts = {}                 # (source sha256, strict) -> True when the general path builds it

    def _run(self, command, timeout, env=None):
        try:
            return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout, env=env or cli._env())
        except (OSError, subprocess.SubprocessError) as error:
            return subprocess.CompletedProcess(command, 2, "", str(error))

    def check(self, path, options):
        done = self._run(cli._sdk_command("check", *options, path), CHECK_TIMEOUT)
        for line in reversed(done.stdout.splitlines()):
            try:
                report = json.loads(line)
            except ValueError:
                continue
            if isinstance(report, dict) and report.get("schema") == "ail.check/1":
                return report
        return None, (done.stderr or done.stdout or "no report")[-400:]

    def builds_on_general_path(self, path, options, digest, env=None):
        """True / False when the full build accepts / refuses the program, None when it cannot be tried."""
        key = (digest, tuple(options))
        if key in self.verdicts:
            return self.verdicts[key]
        env = env or cli._env()
        if not cli.find_c_compiler(env)[0]:
            return None
        cli.prepare_cache(env)
        with tempfile.TemporaryDirectory(prefix="ail-lsp-") as directory:
            done = self._run(cli._sdk_command("compile", *options, path, "-o", Path(directory) / "probe"),
                             BUILD_TIMEOUT, env)
        verdict = done.returncode == 0
        self.verdicts[key] = verdict
        return verdict

    def strict_blockers(self, path, options, digest):
        """Every typed-path blocker, from `compile --strict --json` (schema ail.strict/1; it stops before the C
        compiler, so none is needed). Items shaped like check diagnostics; blockers without a position are left out.
        None when the report is not available."""
        key = ("blockers", digest, tuple(options))
        if key in self.verdicts:
            return self.verdicts[key]
        with tempfile.TemporaryDirectory(prefix="ail-lsp-") as directory:
            done = self._run(cli._sdk_command("compile", "--strict", "--json", *options, path,
                                              "-o", Path(directory) / "probe"), BUILD_TIMEOUT)
        result = None
        for line in done.stdout.splitlines():
            try:
                report = json.loads(line)
            except ValueError:
                continue
            if isinstance(report, dict) and report.get("schema") == "ail.strict/1":
                result = []
                for blocker in report.get("blockers") or []:
                    if not blocker.get("line"):
                        continue
                    where = Path(blocker.get("path") or path)
                    result.append({"code": "type", "message": blocker.get("message") or blocker.get("why") or "",
                                   "path": str(where if where.is_absolute() else Path(path).parent / where),
                                   "line": blocker["line"], "column": blocker.get("column") or 1})
        self.verdicts[key] = result
        return result

    def diagnose(self, path):
        """[(path, line, column, severity, code, message)] for the file; line and column are 1-based or None."""
        try:
            found = project.find(path.parent)
        except project.ProjectError as error:
            found = None
            problems = [(path, 1, 1, ERROR, "project", str(error))]
        else:
            problems = []
        options = found.compiler_options() if found else []
        report = self.check(path, options)
        if isinstance(report, tuple):
            return problems + [(path, 1, 1, ERROR, "check", "ail check failed: " + report[1])]
        found_strict = bool(found and found.strict)
        items = report.get("diagnostics") or []
        if items and report.get("stage") == "type" and items[0].get("code") not in HARD_CODES:
            blockers = self.strict_blockers(path, options, report.get("source_sha256"))
            if blockers:
                items = blockers
        for item in items:
            problems.append(self.classify(path, item, report, options, found_strict))
        for text in report.get("slow_patterns") or []:
            match = SLOW_PATTERN.match(text)
            if match:
                problems.append((Path(match["path"]), int(match["line"]), 1, INFORMATION, "slow", match["text"]))
        return problems

    def classify(self, path, item, report, options, strict):
        """The one place that decides Warning (general path) or Error (refused)."""
        where = Path(item["path"]) if item.get("path") else path
        line, column = item.get("line") or 1, item.get("column") or 1
        message = item.get("message") or "ail check failed"
        code = item.get("code") or "type"
        if code in HARD_CODES or strict or report.get("stage") != "type":
            return (where, line, column, ERROR, code, message)
        verdict = self.builds_on_general_path(path, options, report.get("source_sha256"))
        if verdict is True:
            return (where, line, column, WARNING, "general-path", "runs on the slow general path because " + message)
        if verdict is None:
            return (where, line, column, WARNING, "general-path",
                    "typed path refused: %s (no C compiler found, so it is not known whether the general path "
                    "builds this)" % message)
        return (where, line, column, ERROR, code, message)


def _line_text(path, line):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[line - 1] if 1 <= line <= len(lines) else ""
    except OSError:
        return ""


def to_lsp(problems, opened):
    """LSP diagnostics grouped by URI. A problem in another file (an imported module) is shown on its own file."""
    grouped = {path_to_uri(opened): []}
    for where, line, column, severity, code, message in problems:
        line0 = max(line - 1, 0)
        text = _line_text(where, line)
        start = min(max(column - 1, 0), len(text))
        end = max(len(text), start + 1)
        grouped.setdefault(path_to_uri(where), []).append({
            "range": {"start": {"line": line0, "character": start}, "end": {"line": line0, "character": end}},
            "severity": severity, "code": code, "source": "ail", "message": message})
    return grouped


def hover_for(diagnostics, position):
    for item in diagnostics:
        start, end = item["range"]["start"], item["range"]["end"]
        inside = (start["line"], start["character"]) <= (position["line"], position["character"]) <= (end["line"], end["character"])
        if inside:
            rewrite = rewrite_of(item["message"])
            body = ("**write instead:** " + rewrite) if rewrite else item["message"]
            head = item["message"].split("write instead:")[0].strip()
            value = (head + "\n\n" + body) if rewrite else body
            return {"contents": {"kind": "markdown", "value": value}, "range": item["range"]}
    return None


class Server:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.diagnoser = Diagnoser()
        self.shutdown = False
        self.published = {}                # uri -> diagnostics last published
        self.shown = {}                    # opened uri -> every uri it published to

    # -- framing
    def read(self):
        length = None
        while True:
            line = self.reader.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            name, _, value = line.decode("ascii", errors="replace").partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
        if length is None:
            return None
        return json.loads(self.reader.read(length).decode("utf-8"))

    def send(self, message):
        data = json.dumps(dict(jsonrpc="2.0", **message), ensure_ascii=False).encode("utf-8")
        self.writer.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        self.writer.flush()

    def reply(self, request, result=None, error=None):
        if "id" in request:
            self.send({"id": request["id"], **({"error": error} if error else {"result": result})})

    # -- documents
    def publish(self, uri, diagnostics):
        self.published[uri] = diagnostics
        self.send({"method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": diagnostics}})

    def analyse(self, uri, text=None):
        path = uri_to_path(uri)
        if path is None:
            return
        temporary = None
        try:
            if not path.is_file() and text is not None:
                temporary = tempfile.TemporaryDirectory(prefix="ail-lsp-buffer-")
                path = Path(temporary.name) / (path.name or "buffer.py")
                path.write_text(text, encoding="utf-8")
            grouped = to_lsp(self.diagnoser.diagnose(path), path)
            if temporary is not None:
                grouped = {uri: next(iter(grouped.values()))}
            for other in self.shown.get(uri, set()) - set(grouped):
                self.publish(other, [])
            grouped.setdefault(uri, [])
            for target, items in grouped.items():
                self.publish(target if temporary is None else uri, items)
            self.shown[uri] = set(grouped)
        finally:
            if temporary is not None:
                temporary.cleanup()

    # -- dispatch
    def handle(self, message):
        method, params = message.get("method"), message.get("params") or {}
        if method == "initialize":
            self.reply(message, {"capabilities": {
                "textDocumentSync": {"openClose": True, "change": 0, "save": {"includeText": False}},
                "hoverProvider": True},
                "serverInfo": {"name": "ail-lsp", "version": cli.__version__}})
        elif method == "shutdown":
            self.shutdown = True
            self.reply(message, None)
        elif method == "exit":
            return False
        elif method == "textDocument/didOpen":
            document = params.get("textDocument") or {}
            self.analyse(document.get("uri", ""), document.get("text"))
        elif method == "textDocument/didSave":
            uri = (params.get("textDocument") or {}).get("uri", "")
            self.analyse(uri, params.get("text"))
        elif method == "textDocument/didClose":
            uri = (params.get("textDocument") or {}).get("uri", "")
            for target in self.shown.pop(uri, {uri}):
                self.publish(target, [])
        elif method == "textDocument/hover":
            uri = (params.get("textDocument") or {}).get("uri", "")
            self.reply(message, hover_for(self.published.get(uri, []), params.get("position") or {"line": 0, "character": 0}))
        elif "id" in message and method is not None:
            self.reply(message, error={"code": -32601, "message": "method not found: %s" % method})
        return True

    def run(self):
        while True:
            try:
                message = self.read()
            except (ValueError, OSError):
                return 1
            if message is None:
                return 0 if self.shutdown else 1
            try:
                if not self.handle(message):
                    return 0 if self.shutdown else 1
            except Exception as error:      # one bad request must not end the session
                self.reply(message, error={"code": -32603, "message": "internal error: %s" % error})


def serve(reader=None, writer=None):
    return Server(reader or sys.stdin.buffer, writer or sys.stdout.buffer).run()
