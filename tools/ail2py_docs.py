#!/usr/bin/env python3
"""Rewrite the AIL brace-syntax fenced blocks of a Markdown file as Python.

A block is converted when its fence is ``ail`` / ``ail-refused`` or when
``ail_syntax.detect`` selects the brace front end for its text.  A whole
program keeps its entry function; a fragment without a ``fn`` declaration is
wrapped in ``fn main() -> int { ... return 0; }`` for the conversion and the
wrapper is removed again afterwards.  Converted blocks use the ``python``
fence.  Blocks the converter refuses are left untouched and named on stdout.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIL_CURRENT = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(AIL_CURRENT))
import ail2py  # noqa: E402
import ail_syntax  # noqa: E402


FENCE = re.compile(r'^```(\S*)\s*$')
CLOSE = re.compile(r'^```\s*$')
AIL_FENCES = {'ail', 'ail-refused'}


def _has_top_level_fn(source):
    """True when the block declares a top-level ``fn`` (not just a statement)."""
    try:
        return ail2py._has_entry_main(source) or bool(
            re.search(r'(?m)^\s*fn\s+[A-Za-z_]\w*', source))
    except Exception:
        return bool(re.search(r'(?m)^\s*fn\s+[A-Za-z_]\w*', source))


def _is_fragment(source):
    """True for statements with no top-level declaration to convert on their own."""
    return not re.search(r'(?m)^\s*(fn|const|use|struct|impl)\b', source)


def _wrap(source):
    return 'fn main() -> int {\n' + source.rstrip('\n') + '\n    return 0;\n}\n'


def _unwrap(text):
    """The body of the generated ``main`` without the entry wrapper and its imports."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(r'^def main\(\) -> int:\s*$', line):
            start = index + 1
            break
    if start is None:
        return text
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith('if __name__ == "__main__":'):
            end = index
            break
    body = []
    for line in lines[start:end]:
        if line.startswith('    '):
            body.append(line[4:])
        elif line.strip() == '':
            body.append('')
        else:
            break
    while body and body[-1] == '':
        body.pop()
    head = []
    for line in lines[:start - 1]:
        if line.startswith('def main(') or line.startswith('if __name__'):
            continue
        if line.strip() == '' and not head:
            continue
        head.append(line)
    while head and head[-1] == '':
        head.pop()
    result = head + ([''] if head and body else []) + body
    return '\n'.join(result).rstrip('\n') + '\n'


def convert_block(source):
    """Return Python text for one fenced block, or raise if it cannot be converted."""
    if _is_fragment(source):
        return _unwrap(ail2py.convert(_wrap(source)))
    return ail2py.convert(source)


def process(path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    output = []
    failures = []
    converted = 0
    index = 0
    while index < len(lines):
        match = FENCE.match(lines[index].rstrip('\r\n'))
        if not match:
            output.append(lines[index])
            index += 1
            continue
        language = match.group(1)
        end = index + 1
        while end < len(lines) and not CLOSE.match(lines[end].rstrip('\r\n')):
            end += 1
        if end >= len(lines):
            output.extend(lines[index:])
            break
        body = ''.join(lines[index + 1:end])
        selected = language in AIL_FENCES or ail_syntax.detect(body)
        if not selected:
            output.extend(lines[index:end + 1])
            index = end + 1
            continue
        try:
            python = convert_block(body)
        except Exception as exc:
            failures.append((index + 1, language, str(exc).splitlines()[0]))
            output.extend(lines[index:end + 1])
            index = end + 1
            continue
        newline = '\r\n' if lines[index].endswith('\r\n') else '\n'
        output.append('```python' + newline)
        output.extend(line + newline if not line.endswith(('\n', '\r\n')) else line
                      for line in python.rstrip('\n').split('\n'))
        output.append('```' + newline)
        converted += 1
        index = end + 1
    path.write_text(''.join(output), encoding='utf-8')
    for line, language, message in failures:
        print(f'{path}:{line}: cannot convert ({language}): {message}')
    return converted, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('files', nargs='+', help='Markdown files to rewrite in place')
    args = parser.parse_args(argv)
    status = 0
    for name in args.files:
        converted, failures = process(Path(name))
        print(f'{name}: {converted} block(s) converted, {len(failures)} left')
        if failures:
            status = 1
    return status


if __name__ == '__main__':
    raise SystemExit(main())
