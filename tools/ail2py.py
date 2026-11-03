#!/usr/bin/env python3
"""Convert AIL brace syntax to annotated Python.

The converter is deliberately a thin layer over ``ail_syntax.translate``: the translation is the
front end's own, and this tool only makes the result readable and keeps the source comments.  The
converted file builds to the same C as the brace source when the C markers are removed; ``--check``
compiles both and compares the debug C.
"""
import argparse
import ast
import difflib
import io
import re
import shlex
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIL_CURRENT = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(AIL_CURRENT))
import ail_syntax  # noqa: E402


MARKERS = (
    (re.compile(r'__ail_checked_void__'), 'None'),
    (re.compile(r'__ail_checked_flist__'), 'list[float]'),
    (re.compile(r'__ail_checked_list\['), 'list['),
    (re.compile(r'__ail_checked_(\w+?)__'), r'\1'),
)


def _has_entry_main(source):
    """True when a ``fn main`` is declared at brace depth zero (a top-level function)."""
    depth = 0
    parts = [part for part in tokenize.generate_tokens(io.StringIO(source).readline)
             if part.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                                  tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)]
    for index, part in enumerate(parts):
        if part.type == tokenize.NAME and part.string == 'fn' and depth == 0:
            if index + 1 < len(parts) and parts[index + 1].type == tokenize.NAME \
                    and parts[index + 1].string == 'main':
                return True
        if part.string == '{':
            depth += 1
        elif part.string == '}':
            depth = max(0, depth - 1)
    return False


def _comments(source):
    """The brace source's comments as (line, column, text), in source order."""
    found = []
    for part in tokenize.generate_tokens(io.StringIO(source).readline):
        if part.type == tokenize.COMMENT:
            found.append((part.start[0], part.start[1], part.string.rstrip('\r\n')))
    return found


def _declarations(source):
    """The source lines of ``use`` imports and of each ``struct`` and its fields.

    ``translate`` records no position for the generated ``class``/``__init__``/field lines or for
    the ``use`` imports, so comments around them are placed with this scan.
    """
    structs = {}
    uses = []
    parts = []
    depth = 0
    current = None
    for part in tokenize.generate_tokens(io.StringIO(source).readline):
        if part.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                         tokenize.COMMENT, tokenize.ENDMARKER):
            continue
        if part.type == tokenize.ERRORTOKEN and part.string.isspace():
            continue
        value = part.string
        if value == '{':
            header = ' '.join(item.string for item in parts).strip()
            if depth == 0:
                match = re.fullmatch(r'struct\s+([A-Za-z_]\w*)', header)
                if match:
                    current = match[1]
                    start = parts[0].start[0] if parts else part.start[0]
                    structs[current] = {'line': start, 'fields': []}
            depth += 1
            parts = []
            continue
        if value == '}':
            depth = max(0, depth - 1)
            if depth == 0:
                current = None
            parts = []
            continue
        if value == ';':
            statement = ' '.join(item.string for item in parts).strip()
            start = parts[0].start[0] if parts else part.start[0]
            if depth == 0:
                match = re.fullmatch(r'use\s+([A-Za-z_]\w*)', statement)
                if match:
                    uses.append((match[1], start))
            elif depth == 1 and current is not None:
                match = re.match(r'([A-Za-z_]\w*)\s*:', statement)
                if match:
                    structs[current]['fields'].append((match[1], start))
            parts = []
            continue
        parts.append(part)
    return structs, uses


def _brace_open_lines(source):
    """Map each block-closing ``}`` line to the line that opened that block."""
    opened = []
    parts = []
    result = {}
    for part in tokenize.generate_tokens(io.StringIO(source).readline):
        if part.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                         tokenize.COMMENT, tokenize.ENDMARKER):
            continue
        if part.type == tokenize.ERRORTOKEN and part.string.isspace():
            continue
        value = part.string
        if value == '{':
            opened.append(parts[0].start[0] if parts else part.start[0])
            parts = []
        elif value == '}':
            if opened:
                result.setdefault(part.start[0], opened.pop())
            parts = []
        elif value == ';':
            parts = []
        else:
            parts.append(part)
    return result


def _struct_meta(lines, meta, structs):
    """Give the generated ``class``/``__init__``/field lines the source lines they came from."""
    current = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            match = re.fullmatch(r'class\s+([A-Za-z_]\w*):', stripped)
            current = match[1] if match and match[1] in structs else None
            if current is not None:
                meta[index] = (structs[current]['line'], indent)
            continue
        if current is None:
            continue
        info = structs[current]
        if re.fullmatch(r'def\s+__init__\s*\(\s*self(?:\s*,\s*.*)?\):', stripped):
            meta[index] = (info['line'], indent)
            continue
        match = re.fullmatch(r'self\.([A-Za-z_]\w*)\s*=\s*\1', stripped)
        if match:
            for field, field_line in info['fields']:
                if field == match[1]:
                    meta[index] = (field_line, indent)
                    break


_INT_RESULTS = {'int', '__ail_checked_int__'}
_BOOL_RESULTS = {'bool', '__ail_checked_bool__'}
_MUTATING_METHODS = frozenset((
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse',
    'update', 'setdefault', 'popitem', 'add', 'discard', 'difference_update',
    'intersection_update', 'symmetric_difference_update',
))
_BOOL_METHODS = frozenset((
    'startswith', 'endswith', 'isdigit', 'isalpha', 'isalnum', 'isdecimal', 'isnumeric',
    'isspace', 'isupper', 'islower', 'istitle', 'isnan', 'isinf', 'isfinite',
))


def _annotation_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_bool_expression(node, bool_functions, bool_names=()):
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.BoolOp):
        return all(_is_bool_expression(value, bool_functions, bool_names) for value in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return True
    if isinstance(node, ast.Name):
        return node.id in bool_names
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return True
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in bool_functions:
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in _BOOL_METHODS:
            return True
    return False


def _bool_declarations(tree, bool_functions):
    """Names known to hold a bool (annotations and assignments of bool expressions)."""
    names = set()
    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                if _annotation_name(argument.annotation) in _BOOL_RESULTS:
                    names.add(argument.arg)
        elif isinstance(node, ast.AnnAssign):
            if _annotation_name(node.annotation) in _BOOL_RESULTS \
                    and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            assignments.append(node)
        elif isinstance(node, ast.Assign):
            assignments.append(node)
    changed = True
    while changed:
        changed = False
        for node in assignments:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(isinstance(target, ast.Name) for target in targets):
                continue
            if any(isinstance(target, ast.Name) and target.id in names for target in targets):
                continue
            if isinstance(node.value, ast.Name) and node.value.id in names \
                    or _is_bool_expression(node.value, bool_functions, names):
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in names:
                        names.add(target.id)
                        changed = True
    return names


def _returns_in(body):
    """The ``return`` statements of one function body, not those of a nested function."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return):
            yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                continue
            yield from _returns_in([child])


def _container_annotation(node):
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id in ('list', 'dict', 'set',
                           '__ail_checked_list', '__ail_checked_dict', '__ail_checked_set')
    if isinstance(node, ast.Subscript):
        return _container_annotation(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.startswith(('list[', 'dict[', 'set['))
    return False


def _container_declarations(tree):
    """Names known to hold a list/dict/set (annotations, parameters, fresh values)."""
    names = set()
    fields = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                if _container_annotation(argument.annotation):
                    names.add(argument.arg)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if _container_annotation(node.annotation):
                names.add(node.target.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            init = next((item for item in node.body if isinstance(item, ast.FunctionDef)
                         and item.name == '__init__'), None)
            if init is None:
                continue
            params = {argument.arg: argument.annotation for argument in
                      [*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs]}
            for item in ast.walk(init):
                if isinstance(item, ast.Assign) and len(item.targets) == 1 \
                        and isinstance(item.targets[0], ast.Attribute) \
                        and isinstance(item.targets[0].value, ast.Name) \
                        and item.targets[0].value.id == 'self' \
                        and isinstance(item.value, ast.Name) \
                        and _container_annotation(params.get(item.value.id)):
                    fields.add(item.targets[0].attr)
    assignments = [node for node in ast.walk(tree)
                   if isinstance(node, (ast.Assign, ast.AnnAssign))]
    changed = True
    while changed:
        changed = False
        for node in assignments:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            values = [node.value]
            if any(isinstance(target, ast.Name) and target.id in names for target in targets):
                continue
            if any(isinstance(target, ast.Name) for target in targets) and any(
                    _container_value(value, names, fields) for value in values):
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in names:
                        names.add(target.id)
                        changed = True
    return names, fields


def _container_value(node, names, fields):
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr in fields
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id in _ALIAS_RETURNS[0]
    return False


_ALIAS_RETURNS = [set()]


def _alias_returns(tree):
    """Functions whose result is an existing container (a field or a parameter)."""
    result = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _container_annotation(node.returns):
            continue
        parameters = {argument.arg for argument in
                      [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        for statement in _returns_in(node.body):
            value = statement.value
            if isinstance(value, ast.Attribute) or (isinstance(value, ast.Name) and value.id in parameters):
                result.add(node.name)
                break
    return result


def _struct_containers(tree):
    """Struct constructor parameters whose field type is a list/dict/set."""
    result = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        init = next((item for item in node.body if isinstance(item, ast.FunctionDef)
                     and item.name == '__init__'), None)
        if init is None:
            continue
        params = [*init.args.posonlyargs, *init.args.args]
        if params and params[0].arg == 'self':
            params = params[1:]
        result[node.name] = [index for index, argument in enumerate(params)
                             if _container_annotation(argument.annotation)]
    return result


def _analysis_tree(text, source_path, source):
    """The entry's AST plus the converted local modules, for names and result types."""
    if source_path is None or source is None:
        return ast.parse(text)
    parts = [text]
    for name, path in sorted(_module_closure(source_path, source).items()):
        if path is None:
            continue
        module_text = path.read_text(encoding='utf-8')
        if ail_syntax.detect(module_text):
            module_text = ail_syntax.translate(module_text, module=True, imports=[],
                                               keep_contracts=False)
        parts.append(module_text)
    try:
        return ast.parse('\n'.join(parts))
    except SyntaxError:
        return ast.parse(text)


def _walk_with_function(tree):
    def walk(node, function):
        yield node, function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node
        for child in ast.iter_child_nodes(node):
            yield from walk(child, function)
    yield from walk(tree, None)


def _copy_container_aliases(text, source_path=None, source=None):
    """Write ``.copy()`` where a brace container is stored into a second place and copies."""
    tree = ast.parse(text)
    analysis = _analysis_tree(text, source_path, source)
    _ALIAS_RETURNS[0] = _alias_returns(analysis)
    names, fields = _container_declarations(analysis)
    structs = _struct_containers(analysis)

    def used_after(name, function, call):
        for item in ast.walk(function) if function is not None else ast.walk(tree):
            if isinstance(item, ast.Name) and item.id == name:
                if (item.lineno, item.col_offset) > (call.end_lineno, call.end_col_offset):
                    return True
        return False

    def mutated_after(name, function, node):
        for item in ast.walk(function) if function is not None else ast.walk(tree):
            if (getattr(item, 'lineno', -1), getattr(item, 'col_offset', -1)) <= (node.end_lineno, node.end_col_offset):
                continue
            if isinstance(item, ast.Name) and item.id == name and isinstance(item.ctx, (ast.Store, ast.Del)):
                return True
            if isinstance(item, ast.Subscript) and isinstance(item.ctx, ast.Store) \
                    and isinstance(item.value, ast.Name) and item.value.id == name:
                return True
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) \
                    and isinstance(item.func.value, ast.Name) and item.func.value.id == name \
                    and item.func.attr in _MUTATING_METHODS:
                return True
        return False

    def mutated_attribute_after(base, attr, function, node):
        def is_field(value):
            return isinstance(value, ast.Attribute) and value.attr == attr \
                and isinstance(value.value, ast.Name) and value.value.id == base
        for item in ast.walk(function) if function is not None else ast.walk(tree):
            if (getattr(item, 'lineno', -1), getattr(item, 'col_offset', -1)) <= (node.end_lineno, node.end_col_offset):
                continue
            if isinstance(item, ast.Attribute) and isinstance(item.ctx, (ast.Store, ast.Del)) \
                    and is_field(item):
                return True
            if isinstance(item, ast.Subscript) and isinstance(item.ctx, ast.Store) \
                    and is_field(item.value):
                return True
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) \
                    and item.func.attr in _MUTATING_METHODS and is_field(item.func.value):
                return True
        return False

    targets = []
    for node, function in _walk_with_function(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            assign_targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, (ast.Subscript, ast.Attribute)) for target in assign_targets):
                if not _container_value(value, names, fields):
                    continue
                if isinstance(value, ast.Name):
                    copy = used_after(value.id, function, node)
                elif isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
                        and value.func.id in _ALIAS_RETURNS[0]:
                    copy = any(isinstance(argument, ast.Name)
                               and used_after(argument.id, function, node)
                               for argument in value.args)
                elif isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
                    copy = used_after(value.value.id, function, node)
                else:
                    copy = False
                if copy:
                    targets.append(value)
                continue
            if not all(isinstance(target, ast.Name) for target in assign_targets):
                continue
            if isinstance(value, ast.Name) or \
                    (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                     and value.func.id in _ALIAS_RETURNS[0]):
                if _container_value(value, names, fields):
                    targets.append(value)
            elif isinstance(value, ast.Attribute) and _container_value(value, names, fields):
                target_name = assign_targets[0].id if isinstance(assign_targets[0], ast.Name) else None
                source_name = value.value.id if isinstance(value.value, ast.Name) else None
                if (target_name and mutated_after(target_name, function, node)) or \
                        (source_name and mutated_after(source_name, function, node)):
                    targets.append(value)
        elif isinstance(node, ast.List):
            for element in node.elts:
                if isinstance(element, ast.Name) and _container_value(element, names, fields) \
                        and mutated_after(element.id, function, node):
                    targets.append(element)
                elif isinstance(element, ast.Attribute) and _container_value(element, names, fields) \
                        and isinstance(element.value, ast.Name) \
                        and mutated_attribute_after(element.value.id, element.attr, function, node):
                    targets.append(element)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in structs:
            for index in structs[node.func.id]:
                if index >= len(node.args):
                    continue
                value = node.args[index]
                if isinstance(value, ast.Name) and _container_value(value, names, fields) \
                        and used_after(value.id, function, node):
                    targets.append(value)
    if not targets:
        return text
    spans = sorted({(value.lineno, value.col_offset, value.end_lineno, value.end_col_offset)
                    for value in targets}, reverse=True)
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def position(line, column):
        return starts[line - 1] + column

    for start_line, start_column, end_line, end_column in spans:
        end = position(end_line, end_column)
        text = text[:end] + '.copy()' + text[end:]
    return text


def _wrap_int_bool_returns(text, source_path=None, source=None):
    """In a function whose result is ``int``, write ``int(E)`` for a bool-valued ``return E``."""
    tree = ast.parse(text)
    analysis = _analysis_tree(text, source_path, source)
    bool_functions = {
        node.name for node in ast.walk(analysis)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _annotation_name(node.returns) in _BOOL_RESULTS
    }
    bool_names = _bool_declarations(analysis, bool_functions)
    targets = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _annotation_name(node.returns) not in _INT_RESULTS:
            continue
        for statement in _returns_in(node.body):
            value = statement.value
            if value is not None and _is_bool_expression(value, bool_functions, bool_names):
                targets.append((value.lineno, value.col_offset, value.end_lineno, value.end_col_offset))
    if not targets:
        return text
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def position(line, column):
        return starts[line - 1] + column

    for start_line, start_column, end_line, end_column in sorted(targets, reverse=True):
        start = position(start_line, start_column)
        end = position(end_line, end_column)
        text = text[:start] + 'int(' + text[start:end] + ')' + text[end:]
    return text


def _rewrite_markers(text):
    for pattern, replacement in MARKERS:
        text = pattern.sub(replacement, text)
    return text


def _statement_source_lines(node, rendered):
    """Map a rendered top-level node's statement lines to the brace source line.

    ``node`` is the statement parsed from translate's text, ``rendered`` the AST of its
    ``ast.unparse`` form.  Walking both in the same order pairs each statement with its original
    source position.
    """
    old = [part for part in ast.walk(node) if isinstance(part, ast.stmt)]
    new = [part for part in ast.walk(rendered) if isinstance(part, ast.stmt)]
    if len(old) != len(new):
        return {}
    return {fresh.lineno: original.lineno for original, fresh in zip(old, new)
            if getattr(original, 'lineno', None) is not None}


def _render(text, source_map):
    """Re-render translate's text with ``ast.unparse``, one top-level statement at a time."""
    module = ast.parse(text)
    lines = []
    meta = []
    previous = None
    for node in module.body:
        chunk = ast.unparse(node)
        try:
            rendered = ast.parse(chunk).body[0]
        except (SyntaxError, IndexError):
            rendered = None
        pair = _statement_source_lines(node, rendered) if rendered is not None else {}
        if previous is not None and (
                isinstance(previous, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))):
            lines.append('')
            meta.append(None)
        for relative, line in enumerate(chunk.splitlines(), 1):
            lines.append(line)
            source_line = pair.get(relative)
            position = source_map.get(source_line) if source_line is not None else None
            if position is None:
                meta.append(None)
            else:
                indent = len(line) - len(line.lstrip())
                meta.append((position[0], indent))
        previous = node
    return lines, meta


def _target_at_or_after(meta, line):
    """The first statement at or after ``line`` in source order, not in output order."""
    best = None
    for index, item in enumerate(meta):
        if item is None or item[0] < line:
            continue
        key = (item[0], index)
        if best is None or key < best[0]:
            best = (key, index, item[1])
    return None if best is None else (best[1], best[2])


def _place_comments(lines, meta, comments, source_lines, brace_open_lines):
    for line, column, text in sorted(comments):
        prefix = source_lines[line - 1][:column] if line - 1 < len(source_lines) else ''
        end_of_line = bool(prefix.strip())
        code = prefix.strip()
        target = None
        if end_of_line and code in ('}', '};') and line in brace_open_lines:
            # A comment on a block-closing brace belongs to the block it closes: place it at the
            # opening statement, not at the last statement inside the body.
            target = _target_at_or_after(meta, brace_open_lines[line])
        elif end_of_line:
            # An end-of-line comment belongs to the statement that line closes, even when that
            # statement began on an earlier line.
            for index in range(len(meta) - 1, -1, -1):
                item = meta[index]
                if item is not None and item[0] <= line:
                    target = (index, item[1])
                    break
        else:
            target = _target_at_or_after(meta, line)
        if target is None:
            lines.append('')
            meta.append(None)
            lines.append(text)
            meta.append(None)
        else:
            index, indent = target
            lines.insert(index, ' ' * indent + text)
            meta.insert(index, None)
    return lines


def _entry_block(lines):
    for index in range(len(lines) - 1, -1, -1):
        if lines[index] == 'sys.exit(main())':
            lines[index:index + 1] = ['if __name__ == "__main__":', '    sys.exit(main())']
            return lines
    return lines


def convert(source, source_path=None):
    """Return the annotated Python text for brace ``source``."""
    entry = _has_entry_main(source)
    imports = []
    source_map = {}
    text = ail_syntax.translate(source, module=not entry, imports=imports,
                                keep_contracts=False, source_map=source_map)
    text = _copy_container_aliases(text, source_path, source)
    text = _wrap_int_bool_returns(text, source_path, source)
    text = _rewrite_markers(text)
    structs, uses = _declarations(source)
    lines, meta = _render(text, source_map)
    _struct_meta(lines, meta, structs)
    head = [f'from {name} import *' for name in imports]
    head_meta = [(uses[index][1], 0) if index < len(uses) else None
                 for index in range(len(imports))]
    used = {node.func.id for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ail_syntax.AIL_IMPORT_NAMES}
    if used:
        head.append('from ail import ' + ', '.join(sorted(used)))
        head_meta.append(None)
    lines = head + lines
    meta = head_meta + meta
    lines = _place_comments(lines, meta, _comments(source), source.splitlines(),
                            _brace_open_lines(source))
    if entry:
        lines = _entry_block(lines)
    result = '\n'.join(lines).rstrip('\n') + '\n'
    ast.parse(result)
    return result


def _last_line(data):
    lines = [line.strip() for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


def _run(command):
    return subprocess.run(command, capture_output=True, timeout=1800)


_USE = re.compile(r'^\s*use\s+([A-Za-z_]\w*)\s*;', re.MULTILINE)


def _module_names(text, brace):
    """Names of the local modules ``text`` imports, in source order."""
    if brace:
        return _USE.findall(text)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.append(node.module.split('.')[0])
    return names


def _find_module(name, source_path):
    for directory in (source_path.parent, ROOT / 'language_examples'):
        for suffix in ('.py', '.ail'):
            path = directory / (name + suffix)
            if path.is_file():
                return path
    return None


def _module_closure(source_path, source):
    """The local modules reachable from ``source_path`` through brace ``use`` / Python imports."""
    found = {}
    pending = [(name, source, ail_syntax.detect(source)) for name in _module_names(source, ail_syntax.detect(source))]
    while pending:
        name, text, brace = pending.pop(0)
        if name in found:
            continue
        path = _find_module(name, source_path)
        found[name] = path
        if path is not None:
            module_text = path.read_text(encoding='utf-8')
            pending.extend((child, module_text, ail_syntax.detect(module_text))
                           for child in _module_names(module_text, ail_syntax.detect(module_text)))
    return found


def _stage_converted_modules(work, source_path, source):
    """Write the converted entry and every local module it needs into ``work`` as Python files."""
    work.mkdir(parents=True, exist_ok=True)
    entry = ail_syntax.detect(source)
    closure = _module_closure(source_path, source)
    written = set()
    pending = [(name, source_path) for name in _module_names(source, entry)]
    while pending:
        name, importer = pending.pop(0)
        if name in written:
            continue
        path = closure.get(name) or _find_module(name, source_path)
        if path is None:
            continue
        written.add(name)
        text = path.read_text(encoding='utf-8')
        brace = ail_syntax.detect(text)
        (work / (name + '.py')).write_text(convert(text, path) if brace else text, encoding='utf-8')
        pending.extend((child, path) for child in _module_names(text, brace))
    entry_name = source_path.stem if source_path.suffix == '.py' else 'converted'
    converted_path = work / (entry_name + '.py')
    converted_path.write_text(convert(source, source_path) if entry else source, encoding='utf-8')
    return converted_path, sorted(closure)


def _undo_module_renames(lines, modules):
    result = []
    for line in lines:
        for module in sorted(modules, key=len, reverse=True):
            line = line.replace(module.replace('.', '__') + '__', '')
        result.append(line)
    return result


def _top_level_chunks(lines):
    chunks, chunk, depth = [], [], 0
    for line in lines:
        chunk.append(line)
        depth += line.count('{') - line.count('}')
        if depth < 0:
            depth = 0
        if depth == 0 and (not line.strip() or line.rstrip().endswith(';')):
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    return chunks


def _same_declarations(left, right):
    def chunks(lines):
        normalized = [re.sub(r'ail_fn_[0-9a-f]+', 'ail_fn_HASH', line) for line in lines]
        return sorted(_top_level_chunks(normalized))
    return chunks(left) == chunks(right)


def _difference(left, right):
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    changed = 0
    first = ''
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        changed += max(i2 - i1, j2 - j1)
        if not first:
            first = left[i1] if i1 < len(left) else (right[j1] if j1 < len(right) else '')
    return changed, first


def check(source_path, flags):
    source_path = Path(source_path).resolve()
    source = source_path.read_text(encoding='utf-8')
    converted = convert(source, source_path)
    with tempfile.TemporaryDirectory(prefix='ail2py-') as directory:
        work = Path(directory)
        converted_path, modules = _stage_converted_modules(work / 'converted', source_path, source)
        cli = AIL_CURRENT / 'ail_chatgpt.py'
        original = _run([sys.executable, '-B', str(cli), 'compile', str(source_path),
                         '-o', str(work / 'a'), '--debug-dir', str(work / 'da'), *flags])
        python = _run([sys.executable, '-B', str(cli), 'compile', str(converted_path),
                       '-o', str(work / 'p'), '--syntax', 'python',
                       '--debug-dir', str(work / 'dp'), *flags])
        if original.returncode != 0 and python.returncode != 0:
            print('both-fail')
            return 1
        if original.returncode != 0:
            print('orig-refused: ' + _last_line(original.stderr))
            return 1
        if python.returncode != 0:
            print('py-refused: ' + _last_line(python.stderr))
            return 1
        left = (work / 'da' / 'program.c').read_text(encoding='utf-8').splitlines()
        right = (work / 'dp' / 'program.c').read_text(encoding='utf-8').splitlines()
        if left == right:
            print('identical')
            return 0
        left_names = _undo_module_renames(left, modules)
        right_names = _undo_module_renames(right, modules)
        if left_names == right_names or _same_declarations(left_names, right_names):
            print('identical-renamed')
            return 0
        changed, first = _difference(left, right)
        print(f'differ ({changed} lines; first: {first})')
        return 1


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)
    for index in range(len(argv) - 1):
        if argv[index] == '--flags':
            argv[index] = '--flags=' + argv[index + 1]
            del argv[index + 1]
            break
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('source', help='AIL brace-syntax source (.ail)')
    parser.add_argument('-o', '--output', help='write the Python text here (default: stdout)')
    parser.add_argument('--check', action='store_true',
                        help='compile both forms and compare the generated C')
    parser.add_argument('--flags', default='', help='extra compiler flags for --check')
    args = parser.parse_args(argv)
    try:
        if args.check:
            return check(args.source, shlex.split(args.flags))
        text = convert(Path(args.source).read_text(encoding='utf-8'), Path(args.source).resolve())
    except (OSError, SyntaxError) as exc:
        print(f'ail2py: {exc}', file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
