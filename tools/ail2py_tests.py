#!/usr/bin/env python3
"""Replace embedded brace sources in test modules with the converter's Python text.

The s6 helper scans a test module's string literals for brace declarations (``fn``, ``struct``,
``impl``), converts each one with :func:`tools.ail2py.convert`, and writes the Python text back in
place.  Literals the front end refuses (a deliberate refusal fixture, or a partial source built at
run time) are left untouched and reported; the module is then exercised by the caller.

    python3 -B tools/ail2py_tests.py MODULE...

Only modules under ``AIL_CURRENT/`` are accepted.  Use ``--dry-run`` to list what would change.
"""
import argparse
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / 'AIL_CURRENT'
sys.path.insert(0, str(ROOT / 'tools'))
import ail2py  # noqa: E402

DEFAULT_MODULES = '''test_ail_arg_borrow test_ail_build_cache test_ail_builtin_api test_ail_builtin_contracts test_ail_bytearray_receiver test_ail_callable_owned_results test_ail_callable_values test_ail_csv_writer test_ail_exception_context test_ail_exception_values_app test_ail_finally test_ail_float_argument_widening test_ail_int_dict_set test_ail_lang_gaps test_ail_last_use_free test_ail_memory_shapes test_ail_monotonic test_ail_nested_lists test_ail_numeric_binding_boundaries test_ail_numeric_loop_arena test_ail_numeric_profiles_native test_ail_object_json_query test_ail_ordinary_join_return test_ail_reraise test_ail_silent5 test_ail_stdin_read_until test_ail_str_iter_fast test_ail_struct_list_inplace test_ail_struct_list_objects test_ail_text_views test_ail_try_locals test_ail_type_details test_json_document_library'''.split()

DECLARATION = re.compile(
    r'(?m)(?:^\s*|\n\s*)(?:fn\s+[A-Za-z_]\w*\s*\(|struct\s+[A-Za-z_]\w*|impl\s+[A-Za-z_]\w*)')


def candidate(value):
    return isinstance(value, str) and bool(DECLARATION.search(value))


def same_c(source, converted):
    """True when the brace source and its converted Python text emit the same C."""
    entry = ail2py._has_entry_main(source)
    with tempfile.TemporaryDirectory(prefix='ail2py-test-') as directory:
        work = Path(directory)
        left = work / ('p.ail' if entry else 'p_lib.ail')
        right = work / ('p.py' if entry else 'p_lib.py')
        left.write_text(source, encoding='utf-8')
        right.write_text(converted, encoding='utf-8')
        command = 'compile' if entry else 'compile-module'
        env = dict(os.environ, AIL_NO_CACHE='1', PYTHONUTF8='1')
        outputs = []
        for index, path in enumerate((left, right)):
            debug = work / f'd{index}'
            result = subprocess.run(
                [sys.executable, '-B', str(TESTS / 'ail_chatgpt.py'), command, str(path),
                 *(() if entry else ()), '-o', str(work / f'o{index}'),
                 '--debug-dir', str(debug)], capture_output=True, timeout=180, env=env)
            if result.returncode != 0 or not (debug / 'program.c').is_file():
                return False
            outputs.append((debug / 'program.c').read_text(encoding='utf-8'))
        return outputs[0] == outputs[1]


def quote(text):
    body = text.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
    if body.endswith('"'):
        body = body[:-1] + '\\"'
    return '"""' + body + '"""'


def convert_module(path):
    source = path.read_text(encoding='utf-8')
    lines = source.splitlines(keepends=True)
    starts = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)

    def absolute(position):
        return starts[position[0] - 1] + position[1]

    edits = []
    kept = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.STRING:
            continue
        try:
            value = ast.literal_eval(token.string)
        except (ValueError, SyntaxError):
            continue
        if not candidate(value):
            continue
        try:
            converted = ail2py.convert(value)
        except Exception as exc:  # a refusal fixture or a source assembled at run time
            kept.append((token.start[0], str(exc).splitlines()[0], value))
            continue
        if not same_c(value, converted):
            kept.append((token.start[0], 'C differs', value))
            continue
        edits.append((absolute(token.start), absolute(token.end), quote(converted)))
    if edits:
        for start, end, replacement in sorted(edits, reverse=True):
            source = source[:start] + replacement + source[end:]
        ast.parse(source)
        path.write_text(source, encoding='utf-8')
    return len(edits), kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('modules', nargs='*', default=DEFAULT_MODULES)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    total = 0
    for name in args.modules:
        path = TESTS / (name if name.endswith('.py') else name + '.py')
        if not path.is_file():
            print(f'{name}: missing', file=sys.stderr)
            return 2
        if args.dry_run:
            original = path.read_text(encoding='utf-8')
            count, kept = convert_module(path)
            path.write_text(original, encoding='utf-8')
        else:
            count, kept = convert_module(path)
        total += count
        print(f'{name}: converted {count}')
        for line, reason, value in kept:
            print(f'  kept line {line}: {reason}: {value.splitlines()[0][:70]!r}')
    print(f'total converted {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
