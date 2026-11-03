"""Regenerate AIL_CURRENT/language_examples/STANDARD_SOURCE_API.json from the `.py` twins.

The module list and its order stay as they are; every row is re-read from
`language_examples/<module>.py`:

* `source`, `sha256` and the `dependency_pins` hashes come from the twin bytes;
* `imports` are the twin's `from <module> import *` lines (the converted `use` lines);
* `declared_api` is the twin's own non-underscore declarations;
* `source_check` is `ail_chatgpt.py check <twin> --library --interface` in the syntax the
  compiler detects for it, with diagnostic paths made relative;
* `source_check_all_passed` is true only when every row passed.

Usage:  python3 -B tools/standard_source_api.py [--check]
"""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'AIL_CURRENT'
EXAMPLES = ROOT / 'language_examples'
CATALOG = EXAMPLES / 'STANDARD_SOURCE_API.json'
CLI = ROOT / 'ail_chatgpt.py'

IMPORT = re.compile(r'^from ([A-Za-z_]\w*) import \*', re.M)


def check(source):
    result = subprocess.run([sys.executable, '-B', str(CLI), 'check', str(source), '--library',
                             '--interface'], capture_output=True, text=True, timeout=300)
    return json.loads(result.stdout), result.returncode


def relative(path):
    if not isinstance(path, str):
        return path
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except (OSError, ValueError):
        return path


def source_check(source):
    report, status = check(source)
    diagnostics = []
    for diagnostic in report.get('diagnostics', []):
        diagnostic = dict(diagnostic, path=relative(diagnostic.get('path')))
        if isinstance(diagnostic.get('message'), str):
            diagnostic['message'] = diagnostic['message'].replace(str(REPO) + '/', '')
        diagnostics.append(diagnostic)
    return {
        'status': report.get('status'),
        'checked_functions': report.get('checked_functions'),
        'diagnostics': diagnostics,
        'exit_code': status,
    }


def declared_api(text):
    sys.path.insert(0, str(ROOT))
    import ail_chatgpt
    api = ail_chatgpt._source_interface(ast.parse(text))
    api['functions'] = [f for f in api['functions'] if not f['name'].startswith('_')]
    api['structs'] = [s for s in api['structs'] if not s['name'].startswith('_')]
    return api


def main():
    current = json.loads(CATALOG.read_text(encoding='utf-8'))
    rows = []
    for row in current['modules']:
        source = EXAMPLES / (row['module'] + '.py')
        data = source.read_bytes()
        text = data.decode('utf-8')
        row = dict(row)
        row['source'] = 'language_examples/' + source.name
        row['sha256'] = hashlib.sha256(data).hexdigest()
        row['imports'] = [name for name in IMPORT.findall(text) if name != 'ail']
        row['declared_api'] = declared_api(text)
        row['source_check'] = source_check(source)
        rows.append(row)
    dependencies = sorted({row['source'] for row in rows} |
                          {'language_examples/' + name + '.py' for row in rows for name in row['imports']})
    catalog = dict(current)
    catalog['modules'] = rows
    catalog['source_check_all_passed'] = all(row['source_check']['status'] == 'passed' for row in rows)
    catalog['dependency_pins'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                  for name in dependencies}
    text = json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'
    if '--check' in sys.argv[1:]:
        if CATALOG.read_text(encoding='utf-8') != text:
            print('STANDARD_SOURCE_API.json is stale')
            return 1
        return 0
    CATALOG.write_text(text, encoding='utf-8')
    print('source_check_all_passed =', catalog['source_check_all_passed'])
    for row in rows:
        print(row['module'], row['source_check']['status'], row['source_check']['exit_code'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
