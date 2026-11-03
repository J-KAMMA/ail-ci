"""`ail lsp`: a small language server over stdio (JSON-RPC, Content-Length framing). Standard library only.

* Diagnostics on didOpen, didChange and didSave, from `ail check` (schema ail.check/1). A source that does not
  parse or load is an Error. A program the typed path refuses is built anyway on the slow general path, and the
  server tells the two apart by building it once (a C compiler is needed for that; the result is cached
  per source hash):
    - the build works         Warning "runs on the slow general path because <reason>"
    - the build is refused    Error   "<refusal>" (both carry the compiler's "write instead:" text)
  With `strict = true` in the project (ail.toml / [tool.ail]) every typed-path refusal is an Error.
  `slow_patterns` of the report (quadratic shapes) are Information.
* Hover on a diagnostic shows the rewrite ("write instead: ...") or, when there is none, the message.
  Hover elsewhere shows the type of a name when the front end can tell it (an annotation, or an obvious
  initialiser such as `x = 1`, `xs = [1, 2]`, `s = "hi"`), and a function's signature.
* didChange is full sync (LSP change kind 1). The buffer text is checked, so an unsaved edit still gets
  diagnostics; didSave with no text checks the file on disk.
The blocker list comes from `compile --strict --json` (ail.strict/1: every blocker, with its rewrite); `classify()` decides
Warning or Error.
"""
import ast
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
        key = ("blockers", str(path), digest, tuple(options))
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
                    if not where.is_absolute():
                        # The strict report writes blocker paths relative to the process directory.
                        from_cwd, from_source = Path.cwd() / where, Path(path).parent / where
                        where = from_cwd if from_cwd.exists() or not from_source.exists() else from_source
                    result.append({"code": "type", "message": blocker.get("message") or blocker.get("why") or "",
                                   "path": str(where), "line": blocker["line"],
                                   "column": blocker.get("column") or 1})
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


IDENTIFIER = re.compile(r"[A-Za-z_]\w*")
_CALL_TYPES = {"int": "int", "float": "float", "str": "str", "bool": "bool", "bytes": "bytes",
               "bytearray": "bytearray", "len": "int", "ord": "int", "abs": "int", "round": "int",
               "sum": "int", "input": "str", "list": "list", "dict": "dict", "set": "set",
               "tuple": "tuple", "sorted": "list", "range": "list[int]"}


def _clean_type(text):
    if text is None:
        return None
    text = str(text)
    if text.startswith("__ail_checked_"):
        text = text[len("__ail_checked_"):]
        if text.endswith("__"):
            text = text[:-2]
    return {"flist": "list[float]", "farray": "list[float]"}.get(text, text)


def _annotation(node):
    return _clean_type(ast.unparse(node)) if node is not None else None


def _element_type(kind):
    if kind and kind.startswith("list[") and kind.endswith("]"):
        return kind[5:-1]
    if kind in ("list", "set", "tuple", "range"):
        return None
    if kind and kind.startswith("dict[") and kind.endswith("]"):
        inner = kind[5:-1]
        depth = 0
        for index, char in enumerate(inner):
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            elif char == "," and depth == 0:
                return inner[index + 1:].strip()
    return None


def _value_type(node, env):
    """The type of an initialiser the front end can name from its shape, or None."""
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, bytes):
            return "bytes"
        return None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.JoinedStr):
        return "str"
    if isinstance(node, (ast.List, ast.ListComp)):
        if isinstance(node, ast.List) and not node.elts:
            return "list"
        parts = {_value_type(item, env) for item in node.elts} if isinstance(node, ast.List) else set()
        if len(parts) == 1 and None not in parts:
            return "list[%s]" % parts.pop()
        return "list"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        if isinstance(node, ast.Dict) and node.keys and all(isinstance(k, ast.Constant) for k in node.keys):
            keys = {_value_type(k, env) for k in node.keys}
            values = {_value_type(v, env) for v in node.values}
            if len(keys) == 1 and len(values) == 1 and None not in keys | values:
                return "dict[%s, %s]" % (keys.pop(), values.pop())
        return "dict"
    if isinstance(node, ast.Tuple):
        parts = [_value_type(item, env) for item in node.elts]
        return "tuple[%s]" % ", ".join(part or "?" for part in parts) if parts else "tuple"
    if isinstance(node, ast.UnaryOp):
        return _value_type(node.operand, env)
    if isinstance(node, ast.BoolOp):
        return "bool"
    if isinstance(node, ast.Compare):
        return "bool"
    if isinstance(node, ast.IfExp):
        left, right = _value_type(node.body, env), _value_type(node.orelse, env)
        return left if left == right else None
    if isinstance(node, ast.BinOp):
        left, right = _value_type(node.left, env), _value_type(node.right, env)
        if isinstance(node.op, ast.Mult) and (left in ("list", "str", "bytes") or right in ("list", "str", "bytes")):
            return right if left in ("int",) else left if right in ("int",) else left or right
        if {left, right} <= {"int", "bool"}:
            return "int"
        if left in ("int", "float", "bool") and right in ("int", "float", "bool"):
            return "float" if "float" in (left, right) else "int"
        if left == right and left in ("str", "bytes", "list", "dict", "set"):
            return left
        return None
    if isinstance(node, ast.Subscript):
        base = _value_type(node.value, env)
        return _element_type(base)
    if isinstance(node, ast.Attribute):
        return None
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in _CALL_TYPES:
            kind = _CALL_TYPES[func.id]
            if func.id in ("min", "max") and node.args:
                parts = {_value_type(arg, env) for arg in node.args}
                if len(parts) == 1 and None not in parts:
                    return parts.pop()
            if func.id == "sorted" and node.args:
                element = _element_type(_value_type(node.args[0], env))
                return "list[%s]" % element if element else "list"
            return kind
        if isinstance(func, ast.Attribute):
            if func.attr in ("split", "splitlines"):
                return "list[str]"
            if func.attr in ("strip", "lstrip", "rstrip", "lower", "upper", "replace", "join",
                             "format", "read", "readline"):
                return "str"
            if func.attr in ("keys", "values", "items"):
                base = _value_type(func.value, env)
                if base and base.startswith("dict["):
                    inner = base[5:-1]
                    split = inner.split(", ", 1)
                    if len(split) == 2:
                        return {"keys": "list[%s]" % split[0], "values": "list[%s]" % split[1],
                                "items": "list[tuple[%s, %s]]" % (split[0], split[1])}[func.attr]
            if func.attr == "get" and node.args:
                return _element_type(_value_type(func.value, env))
            if func.attr == "index" and node.args:
                return "int"
        return None
    return None


def _scope_nodes(scope):
    """Nodes of one scope in source order, not descending into nested functions or classes."""
    pending = list(getattr(scope, "body", ()))
    while pending:
        node = pending.pop(0)
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        pending[0:0] = list(ast.iter_child_nodes(node))


def _scope_types(scope):
    env = {}
    args = getattr(scope, "args", None)
    if args is not None:
        for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            kind = _annotation(argument.annotation)
            if kind:
                env[argument.arg] = kind
        for argument in (args.vararg, args.kwarg):
            if argument is not None:
                kind = _annotation(argument.annotation)
                if kind:
                    env[argument.arg] = kind
    for node in _scope_nodes(scope):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            kind = _annotation(node.annotation)
            if kind:
                env[node.target.id] = kind
        elif isinstance(node, ast.Assign):
            kind = _value_type(node.value, env)
            if kind:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = kind
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            kind = _element_type(_value_type(node.iter, env)) or _value_type(node.iter, env)
            if kind:
                env[node.target.id] = kind
        elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            kind = _value_type(node.value, env)
            if kind:
                env[node.target.id] = kind
    return env


def _signature(node):
    arguments = ast.unparse(node.args)
    returns = _annotation(node.returns)
    return "def %s(%s)%s" % (node.name, arguments, " -> %s" % returns if returns else "")


def _position_offset(text, position):
    line = max(int(position.get("line") or 0), 0)
    character = max(int(position.get("character") or 0), 0)
    lines = text.splitlines(keepends=True)
    start = sum(len(item) for item in lines[:line])
    if line >= len(lines):
        return len(text)
    offset = units = 0
    for char in lines[line]:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > character:
            break
        units += width
        offset += 1
    return start + offset


def _name_at(text, position):
    offset = _position_offset(text, position)
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    line = text[start:end if end >= 0 else len(text)]
    column = offset - start
    for match in IDENTIFIER.finditer(line):
        if match.start() <= column < match.end() or (column == match.end() and match.end() == len(line)):
            return match.group()
    return None


def type_hover(text, position):
    """Markdown for the type of the name under the cursor, or None when this front-end view cannot name it."""
    name = _name_at(text, position)
    if name is None:
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    line = int(position.get("line") or 0) + 1
    scopes = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.lineno <= line <= getattr(node, "end_lineno", node.lineno):
            scopes.append(node)
    scopes.sort(key=lambda node: getattr(node, "lineno", 0))
    for scope in reversed(scopes):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and scope.name == name:
            if isinstance(scope, ast.ClassDef):
                return "```python\nclass %s\n```" % scope.name
            return "```python\n%s\n```" % _signature(scope)
    env = {}
    for scope in scopes:
        env.update(_scope_types(scope))
    kind = env.get(name)
    if kind:
        return "`%s`: `%s`" % (name, kind)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "```python\n%s\n```" % _signature(node)
        if isinstance(node, ast.ClassDef) and node.name == name:
            return "```python\nclass %s\n```" % node.name
    return None


def apply_change(text, change):
    """Apply one LSP content change; a change without a range replaces the whole document."""
    replacement = change.get("text") or ""
    selected = change.get("range")
    if not selected:
        return replacement
    start = _position_offset(text, selected.get("start") or {})
    end = _position_offset(text, selected.get("end") or {})
    if start > end:
        start, end = end, start
    return text[:start] + replacement + text[end:]


class Server:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.diagnoser = Diagnoser()
        self.shutdown = False
        self.published = {}                # uri -> diagnostics last published
        self.shown = {}                    # opened uri -> every uri it published to
        self.documents = {}                # uri -> current buffer text

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
        probe, temporary, directory = path, None, None
        try:
            if text is not None:
                # Check the buffer through the same `ail check` the build uses. A sibling file keeps the
                # project, local imports and relative paths intact; a path that has no directory yet is
                # checked in a private temporary directory instead.
                if path.parent.is_dir():
                    handle, name = tempfile.mkstemp(prefix=".ail-lsp-", suffix=path.suffix or ".py",
                                                    dir=str(path.parent))
                    os.close(handle)
                    probe = Path(name)
                    probe.write_text(text, encoding="utf-8")
                else:
                    directory = tempfile.TemporaryDirectory(prefix="ail-lsp-buffer-")
                    probe = Path(directory.name) / (path.name or "buffer.py")
                    probe.write_text(text, encoding="utf-8")
                temporary = probe
            problems = self.diagnoser.diagnose(probe)
            if temporary is not None:
                problems = [(path if Path(where) == temporary else where, line, column, severity, code, message)
                            for where, line, column, severity, code, message in problems]
            grouped = to_lsp(problems, path)
            for other in self.shown.get(uri, set()) - set(grouped):
                self.publish(other, [])
            grouped.setdefault(uri, [])
            for target, items in grouped.items():
                self.publish(target, items)
            self.shown[uri] = set(grouped)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass
            if directory is not None:
                directory.cleanup()

    # -- dispatch
    def handle(self, message):
        method, params = message.get("method"), message.get("params") or {}
        if method == "initialize":
            self.reply(message, {"capabilities": {
                "textDocumentSync": {"openClose": True, "change": 1, "save": {"includeText": False}},
                "hoverProvider": True},
                "serverInfo": {"name": "ail-lsp", "version": cli.__version__}})
        elif method == "shutdown":
            self.shutdown = True
            self.reply(message, None)
        elif method == "exit":
            return False
        elif method == "textDocument/didOpen":
            document = params.get("textDocument") or {}
            uri = document.get("uri", "")
            if document.get("text") is not None:
                self.documents[uri] = document["text"]
            self.analyse(uri, document.get("text"))
        elif method == "textDocument/didChange":
            uri = (params.get("textDocument") or {}).get("uri", "")
            text = self.documents.get(uri)
            if text is None:
                path = uri_to_path(uri)
                text = path.read_text(encoding="utf-8", errors="replace") if path and path.is_file() else ""
            for change in params.get("contentChanges") or []:
                text = apply_change(text, change)
            self.documents[uri] = text
            self.analyse(uri, text)
        elif method == "textDocument/didSave":
            uri = (params.get("textDocument") or {}).get("uri", "")
            if params.get("text") is not None:
                self.documents[uri] = params["text"]
            self.analyse(uri, params.get("text"))
        elif method == "textDocument/didClose":
            uri = (params.get("textDocument") or {}).get("uri", "")
            self.documents.pop(uri, None)
            for target in self.shown.pop(uri, {uri}):
                self.publish(target, [])
        elif method == "textDocument/hover":
            uri = (params.get("textDocument") or {}).get("uri", "")
            position = params.get("position") or {"line": 0, "character": 0}
            answer = hover_for(self.published.get(uri, []), position)
            if answer is None:
                text = self.documents.get(uri)
                if text is None:
                    path = uri_to_path(uri)
                    if path is not None and path.is_file():
                        text = path.read_text(encoding="utf-8", errors="replace")
                if text is not None:
                    value = type_hover(text, position)
                    if value:
                        answer = {"contents": {"kind": "markdown", "value": value}}
            self.reply(message, answer)
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
