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
  Hover elsewhere is certain or absent: a function name shows its signature; a parameter or an annotated
  name shows its annotation; a name whose every assignment in its scope is a literal of one kind
  (int, float, str, bytes, bool or None) shows that kind; anything else shows nothing.
* didChange is full sync (LSP change kind 1). The buffer text is checked, so an unsaved edit still gets
  diagnostics; didSave with no text checks the file on disk.
The blocker list comes from `compile --strict --json` (ail.strict/1: every blocker, with its rewrite); `classify()` decides
Warning or Error.
"""
import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
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

    def check(self, path, options, env=None):
        done = self._run(cli._sdk_command("check", *options, path), CHECK_TIMEOUT, env)
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

    def diagnose(self, path, env=None):
        """[(path, line, column, severity, code, message)] for the file; line and column are 1-based or None."""
        try:
            found = project.find(path.parent)
        except project.ProjectError as error:
            found = None
            problems = [(path, 1, 1, ERROR, "project", str(error))]
        else:
            problems = []
        options = found.compiler_options() if found else []
        report = self.check(path, options, env)
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


def _remap_problems(problems, path, temporary):
    """Point a buffer's diagnostics at the opened file, including any path the compiler printed."""
    names = [str(temporary)]
    if temporary.name not in names:
        names.append(temporary.name)
    result = []
    for where, line, column, severity, code, message in problems:
        if Path(where) == temporary:
            where = path
        for name in names:
            if name and name in message:
                message = message.replace(name, str(path))
        result.append((where, line, column, severity, code, message))
    return result


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


def _annotation(node):
    """The annotation text exactly as the source writes it."""
    return ast.unparse(node) if node is not None else None


def _literal_type(node):
    """The type of a literal of one of the six certain kinds, or None for anything else."""
    if not isinstance(node, ast.Constant):
        return None
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


def _scope_nodes(scope, upto_line=None):
    """Nodes of one scope in source order, not descending into nested functions or classes."""
    pending = list(getattr(scope, "body", ()))
    while pending:
        node = pending.pop(0)
        if upto_line is not None and getattr(node, "lineno", 0) > upto_line:
            continue
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        pending[0:0] = list(ast.iter_child_nodes(node))


def _bind_target(target, uncertain):
    """Record a binding that is not a literal assignment as uncertain."""
    if isinstance(target, ast.Name):
        uncertain.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            _bind_target(item, uncertain)
    elif isinstance(target, ast.Starred):
        _bind_target(target.value, uncertain)


def _scope_info(scope):
    """(annotations, literal_types, uncertain, functions) for one scope.

    `literal_types` is the set of literal kinds assigned to a name; `uncertain` holds a name with
    any non-literal binding. A name is typed only when every assignment in the scope is a literal of
    one kind and nothing else binds it.
    """
    annotations, literals, uncertain, functions = {}, {}, set(), {}

    def annotate(name, text):
        if not text:
            return
        if name in annotations and annotations[name] != text:
            uncertain.add(name)
        else:
            annotations[name] = text

    def assign(target, value):
        if isinstance(target, ast.Name):
            kind = _literal_type(value)
            if kind is None:
                uncertain.add(target.id)
            else:
                literals.setdefault(target.id, set()).add(kind)
        else:
            _bind_target(target, uncertain)

    args = getattr(scope, "args", None)
    if args is not None:
        for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            text = _annotation(argument.annotation)
            if text:
                annotate(argument.arg, text)
            else:
                uncertain.add(argument.arg)
        for argument in (args.vararg, args.kwarg):
            if argument is not None:
                text = _annotation(argument.annotation)
                if text:
                    annotate(argument.arg, text)
                else:
                    uncertain.add(argument.arg)
    for node in _scope_nodes(scope):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotate(node.target.id, _annotation(node.annotation))
            if node.value is not None:
                assign(node.target, node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                assign(target, node.value)
        elif isinstance(node, ast.AugAssign):
            _bind_target(node.target, uncertain)
        elif isinstance(node, ast.NamedExpr):
            assign(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _bind_target(node.target, uncertain)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    _bind_target(item.optional_vars, uncertain)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                uncertain.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                uncertain.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            uncertain.add(node.name)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                uncertain.add(node.name)
    return annotations, literals, uncertain, functions


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
    """The identifier token at a position; strings and comments are not identifiers."""
    offset = _position_offset(text, position)
    lines = text.splitlines(keepends=True)
    starts = []
    total = 0
    for item in lines:
        starts.append(total)
        total += len(item)
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.NAME:
                continue
            row = token.start[0] - 1
            if row < 0 or row >= len(starts):
                continue
            start = starts[row] + token.start[1]
            end = start + len(token.string)
            if start <= offset < end or (offset == end and token.end[1] == len(lines[row].rstrip("\r\n"))):
                return token.string
    except (tokenize.TokenError, IndentationError):
        pass
    return None


def _scopes_at(tree, line):
    """Enclosing module/class/function nodes, outermost first."""
    scopes = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                and node.lineno <= line <= getattr(node, "end_lineno", node.lineno):
            scopes.append(node)
    scopes.sort(key=lambda node: getattr(node, "lineno", 0))
    return scopes


def _function_at(tree, name, line):
    """The function definition a hover on `name` means, preferring the one around the cursor."""
    found = [node for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if not found:
        return None
    found.sort(key=lambda node: node.lineno)
    inside = [node for node in found
              if node.lineno <= line <= getattr(node, "end_lineno", node.lineno)]
    if inside:
        return inside[-1]
    before = [node for node in found if node.lineno <= line]
    return before[-1] if before else found[0]


def type_hover(text, position):
    """Markdown for a certain type or a function signature at the cursor; None when it is not certain."""
    name = _name_at(text, position)
    if name is None:
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    line = int(position.get("line") or 0) + 1
    for scope in reversed(_scopes_at(tree, line)):
        annotations, literals, uncertain, functions = _scope_info(scope)
        if not (name in annotations or name in literals or name in uncertain or name in functions):
            continue
        if name in annotations:
            return "`%s`: `%s`" % (name, annotations[name])
        if name in functions and name not in literals and name not in uncertain:
            return "```python\n%s\n```" % _signature(functions[name])
        if name in uncertain:
            return None
        kinds = literals.get(name) or set()
        if len(kinds) == 1:
            return "`%s`: `%s`" % (name, next(iter(kinds)))
        return None
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
        probe, temporary, directory, env = path, None, None, None
        try:
            if text is not None:
                # Check the buffer through the same `ail check` the build uses. A sibling file keeps the
                # project, local imports and relative paths intact; a read-only directory (or a path
                # that has no directory yet) is checked in a private temporary directory instead, with
                # the real directory first on AIL_PATH so imports still resolve.
                if path.parent.is_dir():
                    try:
                        handle, name = tempfile.mkstemp(prefix=".ail-lsp-", suffix=path.suffix or ".py",
                                                        dir=str(path.parent))
                    except OSError:
                        pass
                    else:
                        os.close(handle)
                        probe = Path(name)
                        probe.write_text(text, encoding="utf-8")
                        temporary = probe
                if temporary is None:
                    directory = tempfile.mkdtemp(prefix="ail-lsp-buffer-")
                    probe = Path(directory) / (path.name or "buffer.py")
                    probe.write_text(text, encoding="utf-8")
                    temporary = probe
                    env = cli._env()
                    existing = env.get("AIL_PATH")
                    env["AIL_PATH"] = str(path.parent) + (os.pathsep + existing if existing else "")
            problems = self.diagnoser.diagnose(probe, env)
            if temporary is not None:
                problems = _remap_problems(problems, path, temporary)
            grouped = to_lsp(problems, path)
            for other in self.shown.get(uri, set()) - set(grouped):
                self.publish(other, [])
            grouped.setdefault(uri, [])
            for target, items in grouped.items():
                self.publish(target, items)
            self.shown[uri] = set(grouped)
        finally:
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)
            elif temporary is not None:
                try:
                    temporary.unlink()
                except OSError:
                    pass

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
