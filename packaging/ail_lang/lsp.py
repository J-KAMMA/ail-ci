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
  (int, float, str, bytes, bool or None) shows that kind; a local the typed path gives a C type shows
  "name: type (inferred by the typed path)", from a --debug build cached per document version (built
  only after didSave or 1 s idle); anything else shows nothing.
* didChange is full sync (LSP change kind 1). The buffer text is checked, so an unsaved edit still gets
  diagnostics; didSave with no text checks the file on disk.
The blocker list comes from `compile --strict --json` (ail.strict/1: every blocker, with its rewrite); `classify()` decides
Warning or Error.
"""
import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
        env = env or cli._env()
        key = (digest, tuple(options), env.get("AIL_PATH") or "")
        if key in self.verdicts:
            return self.verdicts[key]
        if not cli.find_c_compiler(env)[0]:
            return None
        cli.prepare_cache(env)
        with tempfile.TemporaryDirectory(prefix="ail-lsp-") as directory:
            done = self._run(cli._sdk_command("compile", *options, path, "-o", Path(directory) / "probe"),
                             BUILD_TIMEOUT, env)
        verdict = done.returncode == 0
        self.verdicts[key] = verdict
        return verdict

    def strict_blockers(self, path, options, digest, env=None):
        """Every typed-path blocker, from `compile --strict --json` (schema ail.strict/1; it stops before the C
        compiler, so none is needed). Items shaped like check diagnostics; blockers without a position are left out.
        None when the report is not available."""
        env = env or cli._env()
        key = ("blockers", str(path), digest, tuple(options), env.get("AIL_PATH") or "")
        if key in self.verdicts:
            return self.verdicts[key]
        with tempfile.TemporaryDirectory(prefix="ail-lsp-") as directory:
            done = self._run(cli._sdk_command("compile", "--strict", "--json", *options, path,
                                              "-o", Path(directory) / "probe"), BUILD_TIMEOUT, env)
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

    def diagnose(self, path, env=None, source=None):
        """[(path, line, column, severity, code, message)] for the file; line and column are 1-based or None.
        `path` may be a temporary probe for a buffer; `source` is the opened file, whose directory finds the
        project (a read-only directory is checked through a probe in a temporary directory elsewhere)."""
        try:
            found = project.find((source or path).parent)
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
            blockers = self.strict_blockers(path, options, report.get("source_sha256"), env)
            if blockers:
                items = blockers
        for item in items:
            problems.append(self.classify(path, item, report, options, found_strict, env))
        for text in report.get("slow_patterns") or []:
            match = SLOW_PATTERN.match(text)
            if match:
                problems.append((Path(match["path"]), int(match["line"]), 1, INFORMATION, "slow", match["text"]))
        return problems

    def classify(self, path, item, report, options, strict, env=None):
        """The one place that decides Warning (general path) or Error (refused)."""
        where = Path(item["path"]) if item.get("path") else path
        line, column = item.get("line") or 1, item.get("column") or 1
        message = item.get("message") or "ail check failed"
        code = item.get("code") or "type"
        if code in HARD_CODES or strict or report.get("stage") != "type":
            return (where, line, column, ERROR, code, message)
        verdict = self.builds_on_general_path(path, options, report.get("source_sha256"), env)
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
    full, base, real = str(temporary), temporary.name, str(path)
    result = []
    for where, line, column, severity, code, message in problems:
        if Path(where) == temporary:
            where = path
        if message:
            # Replace the full path first so a later base-name replacement cannot split it.
            if full in message:
                message = message.replace(full, real)
            if base != path.name and base in message:
                message = message.replace(base, path.name)
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
    """The annotation text, normalized by ast.unparse (spacing is not preserved)."""
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


_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _scope_roots(scope):
    """The nodes a scope evaluates itself; nested scopes are separate."""
    if isinstance(scope, ast.Lambda):
        return [scope.body]
    if isinstance(scope, ast.DictComp):
        return [scope.key, scope.value]
    if isinstance(scope, _COMPREHENSIONS):
        return [scope.elt]
    return list(getattr(scope, "body", ()))


def _scope_nodes(scope):
    """Nodes of one scope in source order, not descending into nested functions, lambdas, classes
    or comprehensions."""
    pending = list(_scope_roots(scope))
    while pending:
        node = pending.pop(0)
        yield node
        if isinstance(node, _SCOPE_TYPES):
            continue
        pending[0:0] = list(ast.iter_child_nodes(node))


def _new_scope_info():
    return {"annotations": {}, "literals": {}, "uncertain": set(), "functions": {},
            "globals": set(), "nonlocals": set(),
            "global_literals": {}, "global_uncertain": set(),
            "nonlocal_literals": {}, "nonlocal_uncertain": set(),
            "sites": {}, "mutated": set()}


def _add_site(info, name, node, kind, **extra):
    """Record one place that binds `name` in this scope, for go-to-definition."""
    entry = {"node": node, "kind": kind}
    entry.update(extra)
    info["sites"].setdefault(name, []).append(entry)


def _mark_uncertain(name, info):
    """Record a non-literal binding, routed to the global or nonlocal scope it writes."""
    if name in info["globals"]:
        info["global_uncertain"].add(name)
    elif name in info["nonlocals"]:
        info["nonlocal_uncertain"].add(name)
    else:
        info["uncertain"].add(name)


def _mark_literal(name, kind, info):
    """Record one literal kind assigned to a name, routed like `_mark_uncertain`."""
    if name in info["globals"]:
        info["global_literals"].setdefault(name, set()).add(kind)
    elif name in info["nonlocals"]:
        info["nonlocal_literals"].setdefault(name, set()).add(kind)
    else:
        info["literals"].setdefault(name, set()).add(kind)


def _bind_target(target, info, for_iter=None):
    """Record a binding that is not a literal assignment as uncertain."""
    if isinstance(target, ast.Name):
        _mark_uncertain(target.id, info)
        _add_site(info, target.id, target, "assign", for_iter=for_iter)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            _bind_target(item, info, for_iter)
    elif isinstance(target, ast.Starred):
        _bind_target(target.value, info, for_iter)


def _mark_mutated_target(target, mutated):
    """Record the base name of a subscript or attribute store, which mutates that container."""
    if isinstance(target, (ast.Subscript, ast.Attribute)) and isinstance(target.value, ast.Name):
        mutated.add(target.value.id)


def _mutated_names(nodes):
    """Names whose bound value the scope can change, so a literal's elements cannot be trusted.

    A list or dict literal is only evidence for the type of its items while no code mutates it.
    Anything that can change a container — an item or attribute store, `del`, a method call, a
    call that receives it, or an alias assignment — marks the name: the analysis then shows nothing
    rather than a possibly wrong type.
    """
    mutated = set()
    for node in nodes:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets, value = [node.target], getattr(node, "value", None)
        else:
            targets, value = [], None
        for target in targets:
            _mark_mutated_target(target, mutated)
        if isinstance(node, ast.Delete):
            for target in node.targets:
                _mark_mutated_target(target, mutated)
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
                mutated.add(function.value.id)
            for argument in node.args:
                if isinstance(argument, ast.Name):
                    mutated.add(argument.id)
            for keyword in node.keywords:
                if isinstance(keyword.value, ast.Name):
                    mutated.add(keyword.value.id)
        if isinstance(value, ast.Name):
            mutated.add(value.id)
    return mutated


def _pattern_bindings(pattern):
    """The (node, name) pairs a match pattern binds."""
    bindings = []
    for node in ast.walk(pattern):
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bindings.append((node, node.name))
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bindings.append((node, node.rest))
    return bindings


def _scope_info(scope):
    """Bindings of one scope.

    `annotations` maps a parameter or annotated name to its annotation text; `literals` maps a name
    to the set of literal kinds assigned to it; `uncertain` holds a name with any non-literal
    binding; `functions` maps a function name to its definition. Assignments under a `global` or
    `nonlocal` declaration are kept apart so the scope they write can be resolved.
    """
    info = _new_scope_info()
    annotations, literals, uncertain, functions = (info["annotations"], info["literals"],
                                                   info["uncertain"], info["functions"])

    def annotate(name, text):
        if not text:
            return
        if name in info["globals"] or name in info["nonlocals"]:
            return
        if name in annotations and annotations[name] != text:
            annotations.pop(name, None)
            uncertain.add(name)
        else:
            annotations[name] = text

    def assign(target, value):
        if isinstance(target, ast.Name):
            kind = _literal_type(value)
            if kind is None:
                _mark_uncertain(target.id, info)
            else:
                _mark_literal(target.id, kind, info)
            _add_site(info, target.id, target, "assign", value=value)
        else:
            _bind_target(target, info)

    nodes = list(_scope_nodes(scope))
    info["mutated"] = _mutated_names(nodes)
    for node in nodes:
        if isinstance(node, ast.Global):
            info["globals"].update(node.names)
        elif isinstance(node, ast.Nonlocal):
            info["nonlocals"].update(node.names)

    args = getattr(scope, "args", None)
    if args is not None:
        for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            text = _annotation(argument.annotation)
            if text:
                annotate(argument.arg, text)
            else:
                uncertain.add(argument.arg)
            _add_site(info, argument.arg, argument, "param")
        for argument in (args.vararg, args.kwarg):
            if argument is not None:
                text = _annotation(argument.annotation)
                if text:
                    annotate(argument.arg, text)
                else:
                    uncertain.add(argument.arg)
                _add_site(info, argument.arg, argument, "param")
    if isinstance(scope, _COMPREHENSIONS):
        for generator in scope.generators:
            _bind_target(generator.target, info)
    for node in nodes:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotate(node.target.id, _annotation(node.annotation))
            if node.value is not None:
                assign(node.target, node.value)
            else:
                _add_site(info, node.target.id, node.target, "assign", value=None)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                assign(target, node.value)
        elif isinstance(node, ast.AugAssign):
            _bind_target(node.target, info)
        elif isinstance(node, ast.NamedExpr):
            assign(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _bind_target(node.target, info, node.iter)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    _bind_target(item.optional_vars, info)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = (alias.asname or alias.name).split(".")[0]
                _mark_uncertain(bound, info)
                _add_site(info, bound, node, "import", alias=alias)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.asname or alias.name
                _mark_uncertain(bound, info)
                _add_site(info, bound, node, "from-import", alias=alias)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
            _add_site(info, node.name, node, "function")
        elif isinstance(node, ast.ClassDef):
            _mark_uncertain(node.name, info)
            _add_site(info, node.name, node, "class")
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                _mark_uncertain(node.name, info)
                _add_site(info, node.name, node, "except", binding=node.name)
        elif isinstance(node, ast.Match):
            for case in node.cases:
                for binding, name in _pattern_bindings(case.pattern):
                    _mark_uncertain(name, info)
                    _add_site(info, name, binding, "pattern", binding=name)
    return info


def _bound(info, name):
    return (name in info["annotations"] or name in info["literals"] or name in info["uncertain"]
            or name in info["functions"])


def _hover_text(name, info, extra_literals=(), extra_uncertain=False, compiler_type=None, returns=None):
    """The certain hover text for one resolved binding, or None."""
    if name in info["annotations"]:
        return "`%s`: `%s`" % (name, info["annotations"][name])
    kinds = set(info["literals"].get(name, ())) | set(extra_literals)
    uncertain = extra_uncertain or name in info["uncertain"]
    if name in info["functions"] and not kinds and not uncertain:
        return "```python\n%s\n```" % _signature(info["functions"][name])
    if len(kinds) == 1 and not uncertain:
        return "`%s`: `%s`" % (name, next(iter(kinds)))
    inferred = _compiler_hover_type(name, info, compiler_type, returns or {})
    if inferred is not None:
        return "`%s`: `%s` (inferred by the typed path)" % (name, inferred)
    return None


def _signature(node):
    arguments = ast.unparse(node.args)
    returns = _annotation(node.returns)
    return "def %s(%s)%s" % (node.name, arguments, " -> %s" % returns if returns else "")


# ---------------------------------------------------------------- compiler types

# C declarations whose Python type is one-to-one. `int64_t` is handled separately because CPython
# bool is also an int64_t; `ail_nsum` and the numeric box are deliberately absent.
_C_TYPE_NAMES = {
    "int64_t": "int",
    "double": "float",
    "ail_str": "str",
    "ail_bytes": "bytes",
    "ail_slist": "list",
    "ail_list": "list",
    "ail_flist": "list",
    "ail_tab": "dict",
}
_V_DECL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s+(v_[A-Za-z_][A-Za-z0-9_]*)\s*(?:=|;)")
_DEBUG_DECL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_ ]*?)\s+([A-Za-z_][A-Za-z0-9_]*);\s*/\* --debug: the Python local \*/")
_LINE_DIRECTIVE = re.compile(r'^#line\s+(\d+)\s+"([^"]*)"')
_NOT_BOOL_BUILTINS = {"len", "int", "float", "str", "bytes", "list", "dict", "abs", "ord",
                      "chr", "round", "hex", "oct", "bin", "repr"}
_BOOL_METHODS = {"startswith", "endswith", "isdigit", "isalpha", "isalnum", "isspace",
                 "islower", "isupper", "istitle", "isnumeric", "isdecimal", "isidentifier",
                 "isprintable"}
_INT_METHODS = {"count", "find", "rfind", "index", "rindex"}
_STR_METHODS = {"upper", "lower", "strip", "lstrip", "rstrip", "replace", "join", "format",
                "capitalize", "casefold", "center", "expandtabs", "ljust", "rjust", "zfill",
                "title", "swapcase", "removeprefix", "removesuffix"}


def _function_returns(tree):
    """Function name -> return annotation text, for the calls a value may make."""
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.setdefault(node.name, _annotation(node.returns))
    return result


def _binding_values(info, name):
    """(value node, for-iterable) pairs from the assignments of `name` in one scope."""
    result = []
    for site in info["sites"].get(name, []):
        if site.get("kind") != "assign":
            continue
        value, for_iter = site.get("value"), site.get("for_iter")
        if value is not None or for_iter is not None:
            result.append((value, for_iter))
    return result


def _combine_bool(kinds):
    kinds = [kind for kind in kinds if kind != "unknown"]
    if not kinds:
        return "unknown"
    if all(kind == "bool" for kind in kinds):
        return "bool"
    if all(kind == "not-bool" for kind in kinds):
        return "not-bool"
    return "unknown"


def _annotation_kind(text):
    if not text:
        return "unknown"
    text = text.strip()
    if text == "bool":
        return "bool"
    if text in ("int", "float", "str", "bytes", "list", "dict", "None", "NoneType"):
        return "not-bool"
    return "unknown"


def _iterable_element_kind(iterable, info, returns, seen):
    """The kind of the items a literal container yields, or None when it is not a literal.

    A dict yields its keys, not its values; `{**other}` has a key this cannot name.
    """
    if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)):
        return _combine_bool([_bool_kind(item, info, returns, seen) for item in iterable.elts])
    if isinstance(iterable, ast.Dict):
        if any(key is None for key in iterable.keys):
            return "unknown"
        return _combine_bool([_bool_kind(key, info, returns, seen) for key in iterable.keys])
    return None


def _for_iter_kind(iterable, info, returns, seen):
    if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) \
            and iterable.func.id == "range":
        return "not-bool"
    element = _iterable_element_kind(iterable, info, returns, seen)
    if element is not None:
        return element
    if isinstance(iterable, ast.Name):
        if id(iterable) in seen or iterable.id in info["mutated"]:
            return "unknown"
        seen = set(seen)
        seen.add(id(iterable))
        kinds = []
        for bound, for_iter in _binding_values(info, iterable.id):
            if for_iter is not None:
                kinds.append(_for_iter_kind(for_iter, info, returns, seen))
                continue
            element = _iterable_element_kind(bound, info, returns, seen)
            if element is not None:
                kinds.append(element)
            elif isinstance(bound, ast.Name):
                kinds.append(_for_iter_kind(bound, info, returns, seen))
            else:
                kinds.append("unknown")
        return _combine_bool(kinds)
    return "unknown"


def _subscript_kind(value, info, returns, seen):
    container = value.value
    if isinstance(container, (ast.List, ast.Tuple, ast.Set)):
        return _combine_bool([_bool_kind(item, info, returns, seen) for item in container.elts])
    if isinstance(container, ast.Dict):
        return _combine_bool([_bool_kind(item, info, returns, seen) for item in container.values])
    if isinstance(container, ast.Name):
        if container.id in info["mutated"]:
            return "unknown"
        kinds = []
        for bound, for_iter in _binding_values(info, container.id):
            if for_iter is not None:
                kinds.append(_for_iter_kind(for_iter, info, returns, seen))
            elif isinstance(bound, (ast.List, ast.Tuple, ast.Set)):
                kinds.append(_combine_bool([_bool_kind(item, info, returns, seen) for item in bound.elts]))
            elif isinstance(bound, ast.Dict):
                kinds.append(_combine_bool([_bool_kind(item, info, returns, seen) for item in bound.values]))
            else:
                kinds.append("unknown")
        return _combine_bool(kinds)
    return "unknown"


def _bool_kind(value, info, returns, seen):
    """`bool`, `not-bool` or `unknown` for the value of a binding."""
    if value is None:
        return "unknown"
    if id(value) in seen:
        return "unknown"
    seen = set(seen)
    seen.add(id(value))
    if isinstance(value, ast.Constant):
        return "bool" if isinstance(value.value, bool) else "not-bool"
    if isinstance(value, ast.Compare):
        return "bool"
    if isinstance(value, ast.UnaryOp):
        if isinstance(value.op, ast.Not):
            return "bool"
        return "not-bool"
    if isinstance(value, ast.BinOp):
        if isinstance(value.op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            return _combine_bool([_bool_kind(value.left, info, returns, seen),
                                  _bool_kind(value.right, info, returns, seen)])
        return "not-bool"
    if isinstance(value, ast.BoolOp):
        return _combine_bool([_bool_kind(item, info, returns, seen) for item in value.values])
    if isinstance(value, ast.IfExp):
        return _combine_bool([_bool_kind(value.body, info, returns, seen),
                              _bool_kind(value.orelse, info, returns, seen)])
    if isinstance(value, ast.Subscript):
        return _subscript_kind(value, info, returns, seen)
    if isinstance(value, ast.Call):
        function = value.func
        if isinstance(function, ast.Name):
            if function.id in returns:
                return _annotation_kind(returns[function.id])
            if function.id == "bool":
                return "bool"
            if function.id in _NOT_BOOL_BUILTINS:
                return "not-bool"
            return "unknown"
        if isinstance(function, ast.Attribute):
            if function.attr in _BOOL_METHODS:
                return "bool"
            if function.attr in _INT_METHODS or function.attr in _STR_METHODS:
                return "not-bool"
            return "unknown"
        return "unknown"
    if isinstance(value, ast.Name):
        kinds = []
        for bound, for_iter in _binding_values(info, value.id):
            if for_iter is not None:
                kinds.append(_for_iter_kind(for_iter, info, returns, seen))
            else:
                kinds.append(_bool_kind(bound, info, returns, seen))
        return _combine_bool(kinds)
    if isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Lambda,
                          ast.JoinedStr, ast.ListComp, ast.SetComp, ast.DictComp,
                          ast.GeneratorExp)):
        return "not-bool"
    return "unknown"


def _int_kind(name, info, returns):
    """`bool` or `int` for an int64_t binding, or None when the source cannot tell them apart."""
    values = _binding_values(info, name)
    if not values:
        return None
    kinds = []
    for value, for_iter in values:
        if for_iter is not None:
            kinds.append(_for_iter_kind(for_iter, info, returns, set()))
        else:
            kinds.append(_bool_kind(value, info, returns, set()))
    combined = _combine_bool(kinds)
    if combined == "bool":
        return "bool"
    if combined == "not-bool":
        return "int"
    return None


def _compiler_hover_type(name, info, ctype, returns):
    if not ctype:
        return None
    mapped = _C_TYPE_NAMES.get(ctype)
    if mapped == "int":
        return _int_kind(name, info, returns)
    return mapped


def _compiler_type_map(text, path, env, options):
    """(function name, def line) -> {local name: C type}, from a --debug build of the typed path.

    The report names each C function by its mangled name (`outer__helper__0` for a nested `def`),
    not by the Python name the hover sees. The `#line` directives inside the C function's own
    range point at its Python body, so the AST node whose span holds those lines identifies the
    exact scope (a nested function has the same name as a top-level one).
    """
    if not cli.find_c_compiler(env)[0]:
        return {}
    probe, directory = None, None
    if path is not None and path.parent.is_dir():
        try:
            handle, name = tempfile.mkstemp(prefix=".ail-lsp-types-", suffix=path.suffix or ".py",
                                            dir=str(path.parent))
        except OSError:
            pass
        else:
            os.close(handle)
            probe = Path(name)
    if probe is None:
        directory = tempfile.mkdtemp(prefix="ail-lsp-types-")
        probe = Path(directory) / ((path.name if path is not None else None) or "probe.py")
    build_root = tempfile.mkdtemp(prefix="ail-lsp-c-")
    debug = Path(build_root) / "debug"
    try:
        probe.write_text(text, encoding="utf-8")
        build_env = dict(env)
        if directory is not None and path is not None:
            existing = build_env.get("AIL_PATH")
            build_env["AIL_PATH"] = str(path.parent) + (os.pathsep + existing if existing else "")
        command = cli._sdk_command("compile", "--strict", "--debug", "--debug-dir", debug,
                                   *options, probe, "-o", Path(build_root) / "probe")
        try:
            done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=BUILD_TIMEOUT, env=build_env)
        except (OSError, subprocess.SubprocessError):
            return {}
        if done.returncode != 0:
            return {}
        report_path = debug / "native_report.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            lines = (debug / "program.c").read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, ValueError):
            return {}
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return {}
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        source_path = os.path.realpath(str(probe))
        ranges = {}
        for generated in report.get("generated") or []:
            for item in generated.get("functions") or []:
                name = item.get("function")
                start, end = item.get("c_line_start"), item.get("c_line_end")
                if name and start and end:
                    ranges[name] = (start, end)
        result = {}
        for function, (start, end) in ranges.items():
            source_lines = []
            for raw in lines[start - 1:end]:
                directive = _LINE_DIRECTIVE.match(raw)
                if directive and os.path.realpath(directive.group(2)) == source_path:
                    source_lines.append(int(directive.group(1)))
            scope = None
            if source_lines:
                low, high = min(source_lines), max(source_lines)
                containing = [node for node in functions
                              if node.lineno <= low and high <= node.end_lineno]
                if containing:
                    scope = min(containing,
                                key=lambda node: (node.end_lineno - node.lineno, -node.lineno))
            found = {}
            for raw in lines[start - 1:end]:
                match = _V_DECL.match(raw)
                if match:
                    ctype, declared = match.group(1).strip(), match.group(2)
                    if declared.startswith("v__"):
                        continue
                    source = declared[2:] if declared.startswith("v_") else declared
                else:
                    match = _DEBUG_DECL.match(raw)
                    if not match:
                        continue
                    ctype, source = match.group(1).strip(), match.group(2)
                if not source:
                    continue
                previous = found.get(source, ctype)
                found[source] = previous if previous == ctype else None
            if scope is not None:
                result[(scope.name, scope.lineno)] = found
        return result
    finally:
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        elif probe is not None:
            try:
                probe.unlink()
            except OSError:
                pass
        shutil.rmtree(build_root, ignore_errors=True)


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


def _token_at(text, position):
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
                return token
    except (tokenize.TokenError, IndentationError):
        pass
    return None


def _name_at(text, position):
    token = _token_at(text, position)
    return token.string if token is not None else None


def _char_index(text, lineno, byte_column):
    """Absolute character index of an AST position (lineno is 1-based, column is UTF-8 bytes)."""
    lines = text.splitlines(keepends=True)
    if lineno < 1 or lineno > len(lines):
        return None
    line = lines[lineno - 1]
    prefix = line.encode("utf-8")[:byte_column].decode("utf-8", "ignore")
    return sum(len(item) for item in lines[:lineno - 1]) + len(prefix)


def _plain_name_token(text, tree, token):
    """True when the token is a plain name or argument, not an attribute or keyword label."""
    lines = text.splitlines(keepends=True)
    if token.start[0] < 1 or token.start[0] > len(lines):
        return False
    start = sum(len(item) for item in lines[:token.start[0] - 1]) + token.start[1]
    end = start + len(token.string)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.arg)):
            name = node.id if isinstance(node, ast.Name) else node.arg
            if name != token.string:
                continue
            node_start = _char_index(text, node.lineno, node.col_offset)
            if node_start != start:
                continue
            if isinstance(node, ast.arg):
                return True
            if _char_index(text, node.end_lineno, node.end_col_offset) == end:
                return True
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            if token.start[0] == node.lineno and token.string in node.names:
                return True
        elif isinstance(node, ast.ExceptHandler) and node.name == token.string:
            found = _except_name_span(text, node, node.name)
            if found is not None and found[0] == start:
                return True
        elif isinstance(node, ast.Match):
            for case in node.cases:
                for binding, name in _pattern_bindings(case.pattern):
                    if name != token.string:
                        continue
                    found = _name_token_span(text, binding, name)
                    if found is not None and found[0] == start:
                        return True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            line = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
            keyword = "class" if isinstance(node, ast.ClassDef) else "def"
            match = re.search(r"\b" + keyword + r"\s+" + re.escape(node.name) + r"\b", line)
            if match and token.start == (node.lineno, match.end() - len(node.name)) \
                    and token.string == node.name:
                return True
    return False


def _span(text, node):
    """Absolute character span of an AST node, or None."""
    try:
        start = _char_index(text, node.lineno, node.col_offset)
        end = _char_index(text, node.end_lineno, node.end_col_offset)
    except (AttributeError, TypeError):
        return None
    return None if start is None or end is None else (start, end)


def _body_start(text, scope):
    body = getattr(scope, "body", None)
    if isinstance(body, list) and body:
        span = _span(text, body[0])
        return span[0] if span else None
    if isinstance(scope, ast.Lambda):
        span = _span(text, scope.body)
        return span[0] if span else None
    return None


def _in_arguments(text, scope, offset):
    args = getattr(scope, "args", None)
    if args is None:
        return False
    for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
        if argument is None:
            continue
        span = _span(text, argument)
        if span and span[0] <= offset < span[0] + len(argument.arg):
            return True
    return False


def _scope_chain(text, tree, offset):
    """Scopes containing the cursor, outermost first.

    A function's defaults, annotations and decorators are evaluated in the enclosing scope, and a
    parameter name belongs to the function, so only the body and the parameter names include it.
    """
    chain = [tree]

    def visit(node):
        for child in ast.iter_child_nodes(node):
            span = _span(text, child)
            if span is None:
                visit(child)
                continue
            start, end = span
            if not (start <= offset <= end):
                continue
            if isinstance(child, _COMPREHENSIONS):
                generators = child.generators
                first = generators[0].iter if generators else None
                first_span = _span(text, first) if first is not None else None
                if first_span is not None and first_span[0] <= offset <= first_span[1]:
                    # The first iterable of a comprehension runs in the enclosing scope.
                    visit(child)
                    return
            if isinstance(child, _SCOPE_TYPES):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                    body = _body_start(text, child)
                    if body is not None and offset < body and not _in_arguments(text, child, offset):
                        visit(child)
                        return
                chain.append(child)
                visit(child)
                return
            visit(child)

    visit(tree)
    return chain


def _scope_kind(scope):
    if isinstance(scope, ast.Module):
        return "module"
    if isinstance(scope, ast.ClassDef):
        return "class"
    if isinstance(scope, _COMPREHENSIONS):
        return "comprehension"
    return "function"


def _hover_in_chain(tree, chain, name, compiler_types=None):
    """Resolve `name` through the cursor's scopes, then return a certain hover text or None."""
    infos = {}
    compiler_types = compiler_types or {}
    returns = _function_returns(tree)

    def info_for(scope):
        key = id(scope)
        if key not in infos:
            infos[key] = _scope_info(scope)
        return infos[key]

    def compiler_type(scope):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return (compiler_types.get((scope.name, scope.lineno)) or {}).get(name)
        return None

    global_literals, global_uncertain = set(), False
    nonlocal_literals, nonlocal_uncertain = set(), False
    mode = None
    for index in range(len(chain) - 1, -1, -1):
        scope = chain[index]
        info = info_for(scope)
        kind = _scope_kind(scope)
        if kind == "module":
            if mode == "nonlocal":       # a nonlocal declaration cannot reach the module
                return None
            literals = (set(info["literals"].get(name, ())) | set(info["global_literals"].get(name, ()))
                        | global_literals | nonlocal_literals)
            uncertain = (name in info["uncertain"] or name in info["global_uncertain"]
                         or global_uncertain or nonlocal_uncertain)
            return _hover_text(name, info, literals, uncertain, None, returns)
        if kind == "class" and index != len(chain) - 1:
            # A class body is not an enclosing scope for a method, lambda or comprehension.
            continue
        if mode == "global":
            if name in info["globals"]:
                global_literals |= info["global_literals"].get(name, set())
                global_uncertain = global_uncertain or name in info["global_uncertain"]
            continue
        if mode == "nonlocal":
            if kind == "class":
                continue
            if name in info["nonlocals"]:
                nonlocal_literals |= info["nonlocal_literals"].get(name, set())
                nonlocal_uncertain = nonlocal_uncertain or name in info["nonlocal_uncertain"]
                continue
            if _bound(info, name):
                return _hover_text(name, info, nonlocal_literals,
                                   name in info["uncertain"] or nonlocal_uncertain,
                                   compiler_type(scope), returns)
            continue
        if kind in ("function", "comprehension", "class"):
            if name in info["globals"]:
                mode = "global"
                global_literals |= info["global_literals"].get(name, set())
                global_uncertain = global_uncertain or name in info["global_uncertain"]
                continue
            if name in info["nonlocals"]:
                mode = "nonlocal"
                nonlocal_literals |= info["nonlocal_literals"].get(name, set())
                nonlocal_uncertain = nonlocal_uncertain or name in info["nonlocal_uncertain"]
                continue
        if _bound(info, name):
            return _hover_text(name, info, compiler_type=compiler_type(scope), returns=returns)
    return None


# ---------------------------------------------------------------- go-to-definition

def _disk_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


_MODULES = None


def _modules():
    """The compiler's module loader, for its search order (entry directory, AIL_PATH, bundled stdlib)."""
    global _MODULES
    if _MODULES is None:
        sdk = str(cli.SDK)
        if sdk not in sys.path:
            sys.path.insert(0, sdk)
        import ail_modules
        _MODULES = ail_modules
    return _MODULES


def _token_span(text, token):
    lines = text.splitlines(keepends=True)
    row = token.start[0] - 1
    if row < 0 or row >= len(lines):
        return None
    start = sum(len(item) for item in lines[:row]) + token.start[1]
    return start, start + len(token.string)


def _offset_position(text, offset):
    """LSP position of a character offset; `character` counts UTF-16 code units."""
    lines = text.splitlines(keepends=True)
    total = 0
    for index, line in enumerate(lines):
        if total + len(line) > offset:
            prefix = line[:offset - total]
            character = sum(2 if ord(char) > 0xFFFF else 1 for char in prefix)
            return {"line": index, "character": character}
        total += len(line)
    return {"line": max(len(lines) - 1, 0), "character": 0}


def _range_of_span(text, start, end):
    return {"start": _offset_position(text, start), "end": _offset_position(text, end)}


def _node_range(text, node):
    span = _span(text, node)
    if span is None:
        return None
    return _range_of_span(text, *span)


def _definition_span(text, node):
    """The span of a bound name: a def/class name or a parameter rather than the whole statement."""
    if isinstance(node, ast.arg):
        start = _char_index(text, node.lineno, node.col_offset)
        return None if start is None else (start, start + len(node.arg))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        start = _char_index(text, node.lineno, node.col_offset)
        if start is None:
            return None
        prefix = 6 if isinstance(node, ast.ClassDef) else (10 if isinstance(node, ast.AsyncFunctionDef) else 4)
        return start + prefix, start + prefix + len(node.name)
    return _span(text, node)


def _tokens(text):
    try:
        return list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return []


def _name_token_span(text, node, name):
    """The span of the name token `name` inside `node`, so a capture is not the whole pattern."""
    span = _span(text, node)
    if span is None or not name:
        return None
    for token in _tokens(text):
        if token.type != tokenize.NAME or token.string != name:
            continue
        found = _token_span(text, token)
        if found is not None and span[0] <= found[0] and found[1] <= span[1]:
            return found
    return None


def _except_name_span(text, node, name):
    """The span of the `as <name>` binding of an except handler (its header, not its body)."""
    span = _span(text, node)
    if span is None or not name:
        return None
    end = span[1]
    if node.body:
        body_span = _span(text, node.body[0])
        if body_span is not None:
            end = body_span[0]
    previous = None
    for token in _tokens(text):
        found = _token_span(text, token)
        if found is None or found[0] < span[0] or found[1] > end:
            continue
        if token.type == tokenize.NAME:
            if previous == "as" and token.string == name:
                return found
            previous = token.string
    return None


def _location(path, text, node, span=None):
    rng = _range_of_span(text, *span) if span is not None else _node_range(text, node)
    if rng is None:
        return None
    return {"uri": path_to_uri(path), "range": rng}


def _module_location(path):
    zero = {"line": 0, "character": 0}
    return {"uri": path_to_uri(path), "range": {"start": dict(zero), "end": dict(zero)}}


def _dedup(locations):
    seen, result = set(), []
    for item in locations:
        if item is None:
            continue
        start, end = item["range"]["start"], item["range"]["end"]
        key = (item["uri"], start["line"], start["character"], end["line"], end["character"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _find_scope_results(chain, name):
    """The (scope, info) pairs that bind `name`, innermost first, following global/nonlocal declarations."""
    infos = {}

    def info_for(scope):
        key = id(scope)
        if key not in infos:
            infos[key] = _scope_info(scope)
        return infos[key]

    mode = None
    for index in range(len(chain) - 1, -1, -1):
        scope = chain[index]
        info = info_for(scope)
        kind = _scope_kind(scope)
        if kind == "module":
            if mode == "nonlocal":
                return []
            return [(scope, info)]
        if kind == "class" and index != len(chain) - 1:
            continue
        if mode == "global":
            continue
        if mode == "nonlocal":
            if kind == "class":
                continue
            if name in info["nonlocals"]:
                continue
            if _bound(info, name):
                return [(scope, info)]
            continue
        if kind in ("function", "comprehension", "class"):
            if name in info["globals"]:
                mode = "global"
                continue
            if name in info["nonlocals"]:
                mode = "nonlocal"
                continue
        if _bound(info, name):
            return [(scope, info)]
    return []


def _text_of(path, read_text):
    text = read_text(path) if read_text else None
    if text is None:
        text = _disk_text(path)
    return text


def _module_path(name, entry_path, read_text):
    """The file of dotted module `name`, searched as the compiler does (entry dir, AIL_PATH, bundled)."""
    if not name:
        return None
    try:
        program = _modules().Program(Path(entry_path).resolve(),
                                     lambda path: _text_of(Path(path), read_text) or "")
    except Exception:
        return None
    parts = name.split(".")
    dirs = list(program.roots)
    found = None
    for index in range(len(parts)):
        try:
            found = program.spec(".".join(parts[:index + 1]), dirs, None, None)
        except Exception:
            return None
        if found is None:
            return None
        kind, path, mdirs = found
        if kind in ("package", "namespace"):
            dirs = mdirs
        else:
            dirs = []
        if index < len(parts) - 1 and kind == "module":
            return None
    path = found[1] if found else None
    return path if path is not None and Path(path).is_file() else None


def _from_module_path(node, current_path, read_text):
    name = node.module or ""
    level = node.level or 0
    base = current_path.parent
    if level:
        for _ in range(max(level - 1, 0)):
            base = base.parent
        if not name:
            return None
        return _module_path(name, base / "__init__.py", read_text)
    return _module_path(name, current_path, read_text)


def _import_module_path(site, current_path, read_text):
    node, alias = site["node"], site["alias"]
    if isinstance(node, ast.Import):
        return _module_path(_imported_module_name(alias), current_path, read_text)
    if isinstance(node, ast.ImportFrom):
        return _from_module_path(node, current_path, read_text)
    return None


def _module_member_locations(module_path, name, read_text, depth=0):
    if depth > 6 or name == "*":
        return []
    text = _text_of(module_path, read_text)
    if text is None:
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    info = _scope_info(tree)
    return _sites_locations(info["sites"].get(name, []), tree, text, module_path, [tree], read_text, depth + 1)


def _sites_locations(sites, container, text, path, chain, read_text, depth=0):
    locations = []
    for site in sites:
        kind = site["kind"]
        node = site["node"]
        if kind in ("function", "class"):
            locations.append(_location(path, text, node, _definition_span(text, node)))
        elif kind == "param":
            locations.append(_location(path, text, node, _definition_span(text, node)))
        elif kind == "except":
            locations.append(_location(path, text, node, _except_name_span(text, node, site.get("binding"))))
        elif kind == "pattern":
            locations.append(_location(path, text, node, _name_token_span(text, node, site.get("binding"))))
        elif kind in ("import", "from-import"):
            locations += _import_site_locations(site, path, read_text, depth)
        else:
            locations.append(_location(path, text, node))
    return _dedup(locations)


def _imported_module_name(alias):
    """The module a plain `import` binds: `import a.b` binds `a`, but `import a.b as c` binds the module `a.b`."""
    return alias.name if alias.asname else alias.name.split(".")[0]


def _import_site_locations(site, current_path, read_text, depth=0):
    node, alias = site["node"], site["alias"]
    if isinstance(node, ast.Import):
        module_path = _module_path(_imported_module_name(alias), current_path, read_text)
        return [_module_location(module_path)] if module_path else []
    if isinstance(node, ast.ImportFrom):
        module_path = _from_module_path(node, current_path, read_text)
        if module_path is None and node.level and not node.module:
            base = current_path.parent
            for _ in range(max((node.level or 1) - 1, 0)):
                base = base.parent
            module_path = _module_path(alias.name, base / "__init__.py", read_text)
        if module_path is None or alias.name == "*":
            return []
        return _module_member_locations(module_path, alias.name, read_text, depth + 1)
    return []


def _import_hit(text, tree, token):
    """The import statement and alias under the cursor, or the imported module name."""
    span = _token_span(text, token)
    if span is None:
        return None
    start = span[0]
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                row = node.lineno - 1
                if 0 <= row < len(lines):
                    found = lines[row].find(node.module, node.col_offset)
                    if found >= 0:
                        module_start = sum(len(item) for item in lines[:row]) + found
                        if module_start <= start < module_start + len(node.module):
                            return ("module", node)
            for alias in node.names:
                if getattr(alias, "lineno", None) is None:
                    continue
                alias_start = _char_index(text, alias.lineno, alias.col_offset)
                alias_end = _char_index(text, alias.end_lineno, alias.end_col_offset)
                if alias_start is None or alias_end is None:
                    continue
                if alias_start <= start < alias_end:
                    return ("alias", node, alias)
    return None


def _module_hit_locations(hit, current_path, read_text):
    if hit[0] == "module":
        module_path = _from_module_path(hit[1], current_path, read_text)
        return [_module_location(module_path)] if module_path else []
    _, node, alias = hit
    return _import_site_locations({"node": node, "alias": alias,
                                   "kind": "import" if isinstance(node, ast.Import) else "from-import"},
                                  current_path, read_text)


def _attribute_at(text, tree, token):
    span = _token_span(text, token)
    if span is None:
        return None
    start = span[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == token.string:
            end = _char_index(text, node.end_lineno, node.end_col_offset)
            if end is not None and end - len(node.attr) == start:
                return node
    return None


def _nearest_class(chain):
    for scope in reversed(chain):
        if isinstance(scope, ast.ClassDef):
            return scope
    return None


def _class_refs_of_value(value, chain, text, path, read_text, depth):
    refs = []
    if isinstance(value, ast.Call):
        value = value.func
    if isinstance(value, ast.Name):
        for scope, info in _find_scope_results(chain, value.id):
            for site in info["sites"].get(value.id, []):
                if site["kind"] == "class":
                    refs.append((site["node"], text, path))
    return refs


def _class_member_locations(cls, text, path, attr, read_text, depth):
    info = _scope_info(cls)
    return _sites_locations(info["sites"].get(attr, []), cls, text, path, [cls], read_text, depth + 1)


def _attribute_definition(node, chain, text, path, read_text, depth):
    base, attr = node.value, node.attr
    if not isinstance(base, ast.Name):
        return []
    if base.id == "self":
        cls = _nearest_class(chain)
        return _class_member_locations(cls, text, path, attr, read_text, depth) if cls else []
    locations = []
    for scope, info in _find_scope_results(chain, base.id):
        for site in info["sites"].get(base.id, []):
            kind = site["kind"]
            if kind in ("import", "from-import"):
                module_path = _import_module_path(site, path, read_text)
                if module_path:
                    locations += _module_member_locations(module_path, attr, read_text, depth + 1)
            elif kind == "class":
                locations += _class_member_locations(site["node"], text, path, attr, read_text, depth)
            elif kind == "assign":
                for cls, cls_text, cls_path in _class_refs_of_value(site.get("value"), chain, text, path,
                                                                    read_text, depth):
                    locations += _class_member_locations(cls, cls_text, cls_path, attr, read_text, depth)
    return _dedup(locations)


def definition(text, path, position, read_text=None):
    """Go-to-definition locations for the name at the cursor; empty when it cannot be certain."""
    read_text = read_text or _disk_text
    path = Path(path) if path is not None else None
    token = _token_at(text, position)
    if token is None or path is None:
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    attribute = _attribute_at(text, tree, token)
    if attribute is not None:
        offset = _position_offset(text, position)
        return _attribute_definition(attribute, _scope_chain(text, tree, offset), text, path, read_text, 0)
    hit = _import_hit(text, tree, token)
    if hit is not None:
        return _dedup(_module_hit_locations(hit, path, read_text))
    if not _plain_name_token(text, tree, token):
        return []
    offset = _position_offset(text, position)
    chain = _scope_chain(text, tree, offset)
    locations = []
    for scope, info in _find_scope_results(chain, token.string):
        locations += _sites_locations(info["sites"].get(token.string, []), scope, text, path, chain,
                                      read_text, 0)
    return _dedup(locations)


def type_hover(text, position, compiler_types=None):
    """Markdown for a certain type or a function signature at the cursor; None when it is not certain."""
    token = _token_at(text, position)
    if token is None:
        return None
    name = token.string
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    if not _plain_name_token(text, tree, token):
        return None
    offset = _position_offset(text, position)
    return _hover_in_chain(tree, _scope_chain(text, tree, offset), name, compiler_types)


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
        self.versions = {}                 # uri -> document version
        self.changed_at = {}               # uri -> time of the last open/change
        self.saved = set()                 # uris saved since the last change
        self.type_cache = {}               # uri -> ((version, digest), function -> {name: C type})

    def compiler_types(self, uri, text, path):
        """Cached compiler-inferred local types, built only after didSave or 1 s idle."""
        if text is None or path is None:
            return {}
        version = self.versions.get(uri)
        key = (version, hashlib.sha256(text.encode("utf-8")).hexdigest())
        cached = self.type_cache.get(uri)
        if cached is not None and cached[0] == key:
            return cached[1]
        if uri not in self.saved and time.monotonic() - self.changed_at.get(uri, 0.0) < 1.0:
            return {}
        try:
            found = project.find(path.parent)
        except project.ProjectError:
            found = None
        options = found.compiler_options() if found else []
        result = _compiler_type_map(text, path, cli._env(), options)
        self.type_cache[uri] = (key, result)
        return result

    def _open_text(self, path):
        """The buffer text of an open document, so definitions use unsaved edits; None when not open."""
        text = self.documents.get(path_to_uri(path))
        if text is not None:
            return text
        wanted = Path(path).resolve()
        for uri, value in self.documents.items():
            other = uri_to_path(uri)
            if other is not None and Path(other).resolve() == wanted:
                return value
        return None

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
            problems = self.diagnoser.diagnose(probe, env, path)
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
                "hoverProvider": True, "definitionProvider": True},
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
            self.versions[uri] = document.get("version") or 0
            self.changed_at[uri] = time.monotonic()
            self.saved.discard(uri)
            self.type_cache.pop(uri, None)
            self.analyse(uri, document.get("text"))
        elif method == "textDocument/didChange":
            document = params.get("textDocument") or {}
            uri = document.get("uri", "")
            text = self.documents.get(uri)
            if text is None:
                path = uri_to_path(uri)
                text = path.read_text(encoding="utf-8", errors="replace") if path and path.is_file() else ""
            for change in params.get("contentChanges") or []:
                text = apply_change(text, change)
            self.documents[uri] = text
            self.versions[uri] = document.get("version") or self.versions.get(uri) or 0
            self.changed_at[uri] = time.monotonic()
            self.saved.discard(uri)
            self.type_cache.pop(uri, None)
            self.analyse(uri, text)
        elif method == "textDocument/didSave":
            document = params.get("textDocument") or {}
            uri = document.get("uri", "")
            if params.get("text") is not None:
                self.documents[uri] = params["text"]
            if document.get("version") is not None:
                self.versions[uri] = document["version"]
            self.saved.add(uri)
            self.analyse(uri, params.get("text"))
        elif method == "textDocument/didClose":
            uri = (params.get("textDocument") or {}).get("uri", "")
            self.documents.pop(uri, None)
            self.versions.pop(uri, None)
            self.changed_at.pop(uri, None)
            self.saved.discard(uri)
            self.type_cache.pop(uri, None)
            for target in self.shown.pop(uri, {uri}):
                self.publish(target, [])
        elif method == "textDocument/definition":
            document = params.get("textDocument") or {}
            uri = document.get("uri")
            if not uri:
                # A malformed request has no document to look in; keep the old "method not found" reply.
                self.reply(message, error={"code": -32601, "message": "method not found: %s" % method})
            else:
                path = uri_to_path(uri)
                text = self.documents.get(uri)
                if text is None and path is not None and path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                position = params.get("position") or {"line": 0, "character": 0}
                found = definition(text, path, position, self._open_text) if text is not None else []
                self.reply(message, found or None)
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
                    path = uri_to_path(uri)
                    types = self.compiler_types(uri, text, path)
                    value = type_hover(text, position, types)
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
