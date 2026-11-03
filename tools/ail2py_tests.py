#!/usr/bin/env python3
"""Convert embedded brace-syntax sources in test modules to annotated Python.

Each string or bytes literal that is a complete brace-syntax program is converted with
``tools/ail2py.py``'s converter.  A ``translate(<literal>)`` or
``ail_syntax.translate(<literal>)`` wrapper around a converted literal (or a name bound to
one) is removed, because the Python text goes straight to the Python front end.  Literals that
do not convert are left alone; the module still builds them as brace syntax.
"""
import argparse
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'AIL_CURRENT'))
import ail2py  # noqa: E402
import ail_syntax  # noqa: E402


def _brace(value):
    """True when *value* is a complete-looking brace source rather than a Python fragment."""
    if not value.strip():
        return False
    try:
        if ail_syntax.detect(value):
            return True
    except Exception:
        return False
    head = value.lstrip()
    return any(head.startswith(word + ' ') for word in ('fn', 'struct', 'impl', 'const', 'use'))


def _literal(value, as_bytes):
    if as_bytes:
        return repr(value.encode('utf8'))
    return repr(value)


def _name_bindings(tree, converted):
    """Names assigned a single converted literal somewhere in the module."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and id(node.value) in converted:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _translate_call(node):
    if not isinstance(node, ast.Call) or len(node.args) != 1:
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == 'translate'
    return isinstance(node.func, ast.Attribute) and node.func.attr == 'translate'


def convert_module(path, dry_run=False):
    source = path.read_text(encoding='utf8')
    tree = ast.parse(source)
    converted = {}
    skipped = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
            continue
        value = node.value.decode('utf8', 'replace') if isinstance(node.value, bytes) else node.value
        if not _brace(value):
            continue
        try:
            text = ail2py.convert(value)
        except Exception as exc:
            skipped.append((node.lineno, str(exc).splitlines()[0][:120]))
            continue
        converted[id(node)] = (node, _literal(text, isinstance(node.value, bytes)))
    if not converted:
        return 0, skipped
    names = _name_bindings(tree, converted)
    edits = []
    covered = set()
    for node in ast.walk(tree):
        if not _translate_call(node):
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and id(argument) in converted:
            edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset,
                          converted[id(argument)][1]))
            covered.add(id(argument))
        elif isinstance(argument, ast.Name) and argument.id in names:
            edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset,
                          argument.id))
    for ident, (node, text) in converted.items():
        if ident in covered:
            continue
        edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, text))
    data = source.encode('utf8')
    lines = data.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def position(row, column):
        return offsets[row - 1] + column

    pieces = []
    cursor = 0
    for start_row, start_col, end_row, end_col, text in sorted(
            edits, key=lambda item: position(item[0], item[1])):
        start = position(start_row, start_col)
        end = position(end_row, end_col)
        if start < cursor:
            continue
        pieces.append(data[cursor:start])
        pieces.append(text.encode('utf8'))
        cursor = end
    pieces.append(data[cursor:])
    result = b''.join(pieces).decode('utf8')
    ast.parse(result)
    if not dry_run:
        path.write_text(result, encoding='utf8')
    return len(converted), skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='+')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    for name in args.modules:
        path = ROOT / 'AIL_CURRENT' / (name if name.endswith('.py') else name + '.py')
        count, skipped = convert_module(path, args.dry_run)
        print(f'{path.name}: converted {count}, left {len(skipped)}')
        for line, reason in skipped:
            print(f'  line {line}: {reason}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
