#!/usr/bin/env python3
"""Convert embedded brace-syntax sources in test modules to annotated Python.

The converter is ``tools/ail2py.py``'s ``convert`` (the front end's own translation plus the
marker rewrite).  Only complete string literals whose first declaration selects brace syntax are
touched; ``translate(...)`` calls that wrap such a literal (or a module-level name bound to one)
are removed, because the value is already Python.

    python3 -B tools/ail2py_tests.py AIL_CURRENT/test_ail_example.py [...]

Use ``--dry-run`` to print the conversions without writing, and ``--verbose`` to see each one.
"""
import argparse
import ast
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'AIL_CURRENT'))
import ail2py  # noqa: E402
import ail_syntax  # noqa: E402


def _is_brace_source(value):
    if not isinstance(value, str) or 'fn ' not in value:
        return False
    try:
        if not ail_syntax.detect(value):
            return False
    except (tokenize.TokenError, IndentationError):
        return False
    return True


def _literal(value):
    """A string literal whose value is exactly ``value``."""
    if not value.endswith('\\'):
        for quote in ('"""', "'''"):
            if quote not in value:
                return 'r' + quote + value + quote
    return repr(value)


def _offsets(text):
    """Byte offsets of each line start, matching ast's UTF-8 column offsets."""
    data = text.encode('utf8')
    starts = [0]
    for match in __import__('re').finditer(b'\n', data):
        starts.append(match.end())
    return data, starts


def _span(text, node):
    data, starts = _offsets(text)
    start = starts[node.lineno - 1] + node.col_offset
    end = starts[node.end_lineno - 1] + node.end_col_offset
    return data, start, end


def _parents(tree):
    table = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            table[child] = node
    return table


def _assigned_names(tree, converted):
    """Module-level names bound directly to a converted source literal."""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, ast.Constant) and id(value) in converted:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
    return names


def _translate_spans(text, names):
    """Spans of ``translate(x, ...)`` calls whose first argument is already Python."""
    tree = ast.parse(text)
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == 'translate'):
            continue
        if not node.args:
            continue
        arg = node.args[0]
        already = (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                   and not _is_brace_source(arg.value)) \
            or (isinstance(arg, ast.Name) and arg.id in names)
        if already:
            data, start, end = _span(text, node)
            spans.append((start, end, ast.get_source_segment(text, arg) or ast.unparse(arg)))
    return spans


def convert_module(path, dry_run=False, verbose=False):
    text = path.read_text(encoding='utf8')
    tree = ast.parse(text)
    converted = {}
    changes = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and _is_brace_source(node.value)):
            continue
        try:
            output = ail2py.convert(node.value)
        except (SyntaxError, tokenize.TokenError, ail_syntax.SyntaxErrorAIL) as exc:
            if verbose:
                print(f'{path}:{node.lineno}: skip ({exc})')
            continue
        converted[id(node)] = output
        changes.append(node)
    if not changes:
        return 0
    data, starts = _offsets(text)
    spans = []
    for node in changes:
        _, start, end = _span(text, node)
        spans.append((start, end, _literal(converted[id(node)])))
    result = data
    for start, end, replacement in sorted(spans, reverse=True):
        result = result[:start] + replacement.encode('utf8') + result[end:]
    result = result.decode('utf8')
    names = _assigned_names(tree, converted)
    data = result.encode('utf8')
    for start, end, replacement in sorted(_translate_spans(result, names), reverse=True):
        data = data[:start] + replacement.encode('utf8') + data[end:]
    result = data.decode('utf8')
    ast.parse(result)
    if verbose:
        for node in changes:
            print('%s:%d: converted %d bytes' % (path, node.lineno, len(node.value)))
    if not dry_run:
        path.write_text(result, encoding='utf8')
    return len(changes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='+')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    total = 0
    for name in args.modules:
        path = Path(name)
        if not path.is_absolute():
            path = (ROOT / 'AIL_CURRENT' / name) if (ROOT / 'AIL_CURRENT' / name).is_file() else path
        total += convert_module(path, args.dry_run, args.verbose)
    print('%d literal(s) %s' % (total, 'would be converted' if args.dry_run else 'converted'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
