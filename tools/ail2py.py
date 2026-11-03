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


def convert(source):
    """Return the annotated Python text for brace ``source``."""
    entry = _has_entry_main(source)
    imports = []
    source_map = {}
    text = ail_syntax.translate(source, module=not entry, imports=imports,
                                keep_contracts=False, source_map=source_map)
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
    converted = convert(source)
    with tempfile.TemporaryDirectory(prefix='ail2py-') as directory:
        work = Path(directory)
        converted_path = work / 'converted.py'
        converted_path.write_text(converted, encoding='utf-8')
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
        changed, first = _difference(left, right)
        print(f'differ ({changed} lines; first: {first})')
        return 1


TWIN_PREFIX = '# generated by tools/ail2py.py from '
TWIN_SUFFIX = '; edit the .ail until onelang s16'


def twin_header(source):
    return f'{TWIN_PREFIX}{source.name}{TWIN_SUFFIX}'


def _is_twin(text):
    first = text.splitlines()[0] if text.splitlines() else ''
    return first.startswith(TWIN_PREFIX) and first.endswith(TWIN_SUFFIX)


def twins(directory):
    """Write a ``X.py`` twin beside every ``X.ail`` in ``directory``.

    A brace source is converted; a Python-syntax source is copied.  An existing ``X.py`` that was
    not produced by this tool is left alone and listed.
    """
    directory = Path(directory)
    sources = sorted(directory.glob('*.ail'))
    written = 0
    skipped = []
    for source in sources:
        target = source.with_suffix('.py')
        if target.exists() and not _is_twin(target.read_text(encoding='utf-8')):
            skipped.append((source.name, target.name))
            continue
        text = source.read_text(encoding='utf-8')
        body = convert(text) if ail_syntax.detect(text) else text
        if not body.endswith('\n'):
            body += '\n'
        target.write_text(twin_header(source) + '\n' + body, encoding='utf-8')
        written += 1
    for source_name, target_name in skipped:
        print(f'{source_name}: left {target_name} alone (not a twin)', file=sys.stderr)
    print(f'{written} twin(s) written, {len(skipped)} skipped')
    return 0


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
    parser.add_argument('source', nargs='?', help='AIL brace-syntax source (.ail)')
    parser.add_argument('-o', '--output', help='write the Python text here (default: stdout)')
    parser.add_argument('--twins', metavar='DIR',
                        help='write a .py twin beside every .ail in DIR')
    parser.add_argument('--check', action='store_true',
                        help='compile both forms and compare the generated C')
    parser.add_argument('--flags', default='', help='extra compiler flags for --check')
    args = parser.parse_args(argv)
    if args.twins is not None:
        if args.source is not None or args.output is not None or args.check:
            parser.error('--twins takes no source, output or --check')
        try:
            return twins(args.twins)
        except (OSError, SyntaxError) as exc:
            print(f'ail2py: {exc}', file=sys.stderr)
            return 1
    if args.source is None:
        parser.error('a source is required unless --twins is given')
    try:
        if args.check:
            return check(args.source, shlex.split(args.flags))
        text = convert(Path(args.source).read_text(encoding='utf-8'))
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
