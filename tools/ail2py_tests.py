#!/usr/bin/env python3
"""Convert embedded AIL brace sources in a test module to annotated Python text.

    python3 tools/ail2py_tests.py AIL_CURRENT/test_ail_foo.py ...

Each string/bytes constant whose first two tokens select the brace surface is converted with
``tools/ail2py.convert`` (entry text when it declares ``fn main``) and the literal is rewritten in
place.  A literal that cannot be converted, or that the test uses to exercise the brace front end,
is left alone and recorded in ``AIL_CURRENT/onelang_brace_only.txt`` as ``module:line: reason``.
"""
import argparse
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
AIL_CURRENT = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(AIL_CURRENT))
sys.path.insert(0, str(ROOT / 'tools'))
import ail_syntax  # noqa: E402
import ail2py  # noqa: E402

RECORD = AIL_CURRENT / 'onelang_brace_only.txt'


def _line_starts(data):
    return [0, *(index + 1 for index, byte in enumerate(data) if byte == 10)]


def _offset(starts, line, column):
    return starts[line - 1] + column


def _parents(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _brace_front_end(node, parents):
    """A reason when the literal is handed to the brace parser on purpose, else None."""
    parent = parents.get(id(node))
    while parent is not None and isinstance(parent, (ast.keyword, ast.Tuple, ast.List)):
        parent = parents.get(id(parent))
    if isinstance(parent, ast.Call):
        func = parent.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')
        if name in ('translate', 'detect', 'ail_sexpr', 'to_block', 'ail_array_surface'):
            return 'brace-front-end'
        if name in ('main',) and any(isinstance(arg, ast.Constant) and arg.value == 'ail'
                                     for arg in parent.args):
            return 'explicit ail syntax'
    if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Mod):
        return 'formatted source'
    if isinstance(parent, ast.JoinedStr):
        return 'f-string source'
    return None


def _literal(value, was_bytes):
    return repr(value.encode('utf8') if was_bytes else value)


def convert_module(path, record):
    source = path.read_bytes()
    text = source.decode('utf8')
    tree = ast.parse(text)
    parents = _parents(tree)
    starts = _line_starts(source)
    edits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
            continue
        value = node.value
        content = value.decode('utf8', 'replace') if isinstance(value, bytes) else value
        try:
            if not ail_syntax.detect(content):
                continue
        except Exception:
            continue
        reason = _brace_front_end(node, parents)
        converted = None
        if reason is None:
            try:
                converted = ail2py.convert(content)
            except Exception as error:                       # converter refused: keep the brace text
                reason = 'converter: ' + str(error).splitlines()[0]
        if reason is not None:
            record.append('%s:%s: %s' % (path.name, node.lineno, reason))
            continue
        replacement = _literal(converted, isinstance(node.value, bytes))
        start = _offset(starts, node.lineno, node.col_offset)
        end = _offset(starts, node.end_lineno, node.end_col_offset)
        edits.append((start, end, replacement.encode('utf8')))
    if not edits:
        return 0
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    path.write_bytes(source)
    return len(edits)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='+')
    args = parser.parse_args(argv)
    record = []
    if RECORD.exists():
        record = [line for line in RECORD.read_text(encoding='utf8').splitlines() if line.strip()]
    changed = 0
    for name in args.modules:
        path = Path(name)
        if not path.is_file():
            path = AIL_CURRENT / name
        count = convert_module(path, record)
        print('%s: %d literal%s converted' % (path.name, count, '' if count == 1 else 's'))
        changed += count
    if record:
        RECORD.write_text('\n'.join(dict.fromkeys(record)) + '\n', encoding='utf8')
    return 0 if changed or record else 1


if __name__ == '__main__':
    raise SystemExit(main())
