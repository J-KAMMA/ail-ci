#!/usr/bin/env python3
"""Convert embedded brace-syntax sources in test modules to annotated Python.

Usage: python3 tools/ail2py_tests.py MODULE.py ...

For every string (or bytes) literal whose text ``ail_syntax.detect`` reports as brace syntax,
the literal is replaced by the converter's Python text.  Literals that a test deliberately feeds
to the brace front end, that are built by f-string/%-formatting, that appear in an assertion, or
that the converter cannot handle are left alone and listed in AIL_CURRENT/onelang_brace_only.txt.
"""
import argparse
import ast
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIL_CURRENT = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(AIL_CURRENT))
sys.path.insert(0, str(ROOT / 'tools'))

import ail_syntax  # noqa: E402
from ail2py import convert  # noqa: E402


SKIP_FILE = AIL_CURRENT / 'onelang_brace_only.txt'
FRONT_END = {'translate', 'detect', 'ail_sexpr', 'ail_sexpr_parse'}


def _parents(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _call_name(node):
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    return ''


def _ancestors(node, parents):
    seen = set()
    current = parents.get(node)
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = parents.get(current)


def _skip_reason(node, parents, module_text, assertion_functions=()):
    """Why a brace literal must stay brace text, or '' when it may be converted."""
    for ancestor in _ancestors(node, parents):
        if isinstance(ancestor, ast.Call):
            name = _call_name(ancestor)
            if name in FRONT_END:
                return 'front-end ' + name
            if name.startswith('assert'):
                return 'assertion'
            if name in assertion_functions:
                return 'refusal assertion'
        if isinstance(ancestor, (ast.Assert, ast.Compare)):
            return 'assertion'
        if isinstance(ancestor, ast.BinOp) and isinstance(ancestor.op, ast.Mod):
            return 'percent-format'
        if isinstance(ancestor, ast.Call) and isinstance(ancestor.func, ast.Attribute) \
                and ancestor.func.attr in ('format', 'join') and node in ancestor.args:
            return 'format'
        if isinstance(ancestor, ast.Call) and isinstance(ancestor.func, ast.Attribute) \
                and ancestor.func.attr == 'replace' and node in ancestor.args:
            return 'replace pattern'
        if isinstance(ancestor, ast.AugAssign):
            return 'augmented source'
        if isinstance(ancestor, ast.JoinedStr):
            return 'f-string'
    if re.search(r"(?:--syntax[\'\"\s,]*|syntax\s*=\s*)[\'\"]?ail\b", module_text):
        # A literal in a module that explicitly selects the brace front end may be the subject.
        for ancestor in _ancestors(node, parents):
            if isinstance(ancestor, (ast.Assign, ast.AnnAssign, ast.Call)):
                return 'syntax ail'
    return ''



def _names_in(node):
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _defined_frontend_functions(tree):
    """Function names whose bodies reach the brace front end (translate/detect/ail_sexpr)."""
    names = set(FRONT_END)
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    changed = True
    while changed:
        changed = False
        for function in functions:
            if function.name in names:
                continue
            for call in ast.walk(function):
                if isinstance(call, ast.Call) and _call_name(call) in names:
                    names.add(function.name)
                    changed = True
                    break
    return names


def _imported_frontend_functions(tree, path):
    """Front-end helper names imported from sibling test modules."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        target = path.parent / (node.module.replace('.', '/') + '.py')
        if not target.is_file():
            continue
        try:
            imported = ast.parse(target.read_text(encoding='utf8'))
        except (OSError, SyntaxError):
            continue
        local = _defined_frontend_functions(imported)
        for alias in node.names:
            if alias.name in local or alias.name == '*':
                names.add(alias.asname or alias.name)
    return names



def _assertion_functions(tree):
    """Function names that assert: their literal arguments are expected brace refusals."""
    names = set()
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if 'refus' in function.name or function.name.startswith('assert'):
                if any(isinstance(node, ast.Assert) or
                       isinstance(node, ast.Call) and _call_name(node).startswith('assert')
                       for node in ast.walk(function)):
                    names.add(function.name)
    return names


def _imported_assertion_functions(tree, path):
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        target = path.parent / (node.module.replace('.', '/') + '.py')
        if not target.is_file():
            continue
        try:
            imported = ast.parse(target.read_text(encoding='utf8'))
        except (OSError, SyntaxError):
            continue
        local = _assertion_functions(imported)
        for alias in node.names:
            if alias.name in local or alias.name == '*':
                names.add(alias.asname or alias.name)
    return names


def _tainted_names(tree, frontend):
    """Names that stand for brace text handed to a front-end helper, directly or indirectly."""
    tainted = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign):
            tainted |= {child.id for child in ast.walk(node.target)
                        if isinstance(child, ast.Name)}
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and isinstance(node, ast.AugAssign):
                    tainted.add(target.id)
        if isinstance(node, ast.Call) and _call_name(node) in frontend:
            for argument in list(node.args) + [kw.value for kw in node.keywords]:
                tainted |= _names_in(argument)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                target_names = set()
                for target in targets:
                    target_names |= {child.id for child in ast.walk(target)
                                     if isinstance(child, ast.Name)}
                value = node.value
                if value is None:
                    continue
                value_names = _names_in(value)
                added = (target_names & tainted and value_names) or (value_names & tainted and target_names)
                if added:
                    before = len(tainted)
                    tainted |= added
                    changed = changed or len(tainted) != before
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                target_names = {child.id for child in ast.walk(node.target)
                                if isinstance(child, ast.Name)}
                value_names = _names_in(node.iter)
                added = (target_names & tainted and value_names) or (value_names & tainted and target_names)
                if added:
                    before = len(tainted)
                    tainted |= added
                    changed = changed or len(tainted) != before
    return tainted


def _inside_tainted(node, parents, tainted):
    """True when a literal feeds a name that the test later passes to the brace front end."""
    current = node
    for ancestor in _ancestors(node, parents):
        if isinstance(ancestor, (ast.Assign, ast.AnnAssign)):
            targets = ancestor.targets if isinstance(ancestor, ast.Assign) else [ancestor.target]
            for target in targets:
                names = {child.id for child in ast.walk(target) if isinstance(child, ast.Name)}
                if names & tainted:
                    return True
        if isinstance(ancestor, (ast.For, ast.AsyncFor)):
            names = {child.id for child in ast.walk(ancestor.target) if isinstance(child, ast.Name)}
            if names & tainted:
                return True
        current = ancestor
    return False


def _literal_prefix(segment):
    match = re.match(r'(?is)^([rubf]*)("""|\'\'\'|"|\')', segment)
    if not match:
        return '', ''
    return match.group(1).lower(), match.group(2)


def _escape_str(value, delimiter):
    out = []
    for character in value:
        if character == '\\':
            out.append('\\\\')
        elif character == '\r':
            out.append('\\r')
        elif character == delimiter[0]:
            out.append('\\' + character)
        elif ord(character) < 32 and character not in '\n\t':
            out.append('\\x%02x' % ord(character))
        else:
            out.append(character)
    return ''.join(out)


def _escape_bytes(value, delimiter):
    out = []
    for byte in value:
        character = chr(byte)
        if character == '\\':
            out.append('\\\\')
        elif character == '\n' or character == '\t':
            out.append(character)
        elif character == delimiter[0]:
            out.append('\\' + character)
        elif 32 <= byte < 127:
            out.append(character)
        else:
            out.append('\\x%02x' % byte)
    return ''.join(out)


def _make_literal(value, segment, is_bytes):
    prefix, delimiter = _literal_prefix(segment)
    data = value.encode('utf8') if is_bytes else value
    multiline = (b'\n' in data) if is_bytes else ('\n' in data)
    if delimiter in ('"""', "'''"):
        chosen = delimiter
    elif multiline:
        chosen = "'''" if "'''" not in (data.decode('utf8', 'replace') if is_bytes else data) else '"""'
    else:
        chosen = "'"
    if chosen == "'":
        return ('b' if is_bytes else '') + repr(data)
    if is_bytes:
        body = _escape_bytes(data, chosen)
        return 'b' + chosen + body + chosen
    body = _escape_str(data, chosen)
    return chosen + body + chosen


def _line_starts(data):
    starts = [0]
    for line in data.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


def _span(node, starts):
    start = starts[node.lineno - 1] + node.col_offset
    end = starts[node.end_lineno - 1] + node.end_col_offset
    return start, end


def _constant_text(node):
    if isinstance(node.value, str):
        return node.value, False
    if isinstance(node.value, bytes):
        try:
            return node.value.decode('utf8'), True
        except UnicodeDecodeError:
            return None, True
    return None, False


def _joined_text(node):
    pieces = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            pieces.append(child.value)
    return ''.join(pieces)


def convert_module(path, skip_lines=()):
    text = path.read_text(encoding='utf8')
    data = text.encode('utf8')
    starts = _line_starts(data)
    tree = ast.parse(text)
    parents = _parents(tree)
    frontend = _defined_frontend_functions(tree) | _imported_frontend_functions(tree, path)
    assertions = _assertion_functions(tree) | _imported_assertion_functions(tree, path)
    tainted = _tainted_names(tree, frontend)
    replacements = []
    skipped = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            joined = _joined_text(node)
            try:
                brace = bool(joined and ail_syntax.detect(joined))
            except Exception:
                brace = 'fn main(' in joined
            if brace:
                skipped.append((node.lineno, 'f-string'))
            continue
        if not isinstance(node, ast.Constant):
            continue
        source, is_bytes = _constant_text(node)
        if source is None:
            continue
        try:
            brace = ail_syntax.detect(source)
        except Exception:
            brace = False
        if not brace:
            continue
        reason = _skip_reason(node, parents, text, assertions)
        if not reason and _inside_tainted(node, parents, tainted):
            reason = 'front-end variable'
        if node.lineno in skip_lines:
            reason = 'meaning difference (listed)'
        if reason:
            skipped.append((node.lineno, reason))
            continue
        try:
            converted = convert(source)
        except Exception as error:  # the converter refuses some brace shapes
            skipped.append((node.lineno, 'converter: ' + type(error).__name__))
            continue
        start, end = _span(node, starts)
        segment = data[start:end].decode('utf8')
        literal = _make_literal(converted, segment, is_bytes)
        replacements.append((start, end, literal))
    for start, end, literal in sorted(replacements, reverse=True):
        data = data[:start] + literal.encode('utf8') + data[end:]
    if replacements:
        path.write_text(data.decode('utf8'), encoding='utf8')
    return len(replacements), skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='+')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip', action='append', default=[],
                        help='MODULE:LINE of a literal to leave as brace text')
    args = parser.parse_args(argv)
    listed = []
    skips = {}
    for item in args.skip:
        module, _, line = item.rpartition(':')
        skips.setdefault(module, set()).add(int(line))
    for name in args.modules:
        path = Path(name)
        if not path.is_file():
            path = AIL_CURRENT / name
        count, skipped = convert_module(path, skips.get(path.name, ()))
        print('%s: %d converted, %d skipped' % (path.name, count, len(skipped)))
        module = path.name
        for line, reason in sorted(skipped):
            listed.append('%s:%d %s' % (module, line, reason))
    if listed and not args.dry_run:
        existing = []
        if SKIP_FILE.exists():
            existing = [line for line in SKIP_FILE.read_text(encoding='utf8').splitlines() if line.strip()]
        seen = set(existing)
        with SKIP_FILE.open('a', encoding='utf8') as stream:
            for line in listed:
                if line not in seen:
                    stream.write(line + '\n')
                    seen.add(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
