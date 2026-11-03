#!/usr/bin/env python3
"""Check the CPython hybrid against CPython on the compare-lab tasks and the corpus.

    python3 lab/hybrid/check.py [--json lab/hybrid/results.json] [--keep]

For each program the hybrid is built into a fresh temporary directory, then the generated
`<stem>_run.py` and the original source are run with the same stdin and arguments.  stdout, exit
status and the last stderr line must agree; each run has a 60-second timeout.  The program list is
the 10 `lab/compare/src/<task>/main.py` (with the compare-lab performance input and arguments) and
the first 30 `lab/corpus/programs/*/t*.py` sorted by path (stdin from /dev/null).
"""
import argparse
import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT'
COMPARE = REPO / 'lab' / 'compare'
CORPUS = REPO / 'lab' / 'corpus' / 'programs'
TIMEOUT = 60

sys.path.insert(0, str(AIL))
import ail_cpython_hybrid  # noqa: E402


def _load_run_task():
    path = COMPARE / 'run_task.py'
    spec = importlib.util.spec_from_file_location('ail_compare_run_task', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _top_level_count(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in tree.body)


def _last_line(data):
    text = data.decode('utf-8', 'replace').rstrip('\n')
    lines = text.splitlines()
    return lines[-1] if lines else ''


def _first_diff(want, got):
    a = want.decode('utf-8', 'replace').splitlines()
    b = got.decode('utf-8', 'replace').splitlines()
    if not a and not b:
        return None
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<missing line>'
        y = b[i] if i < len(b) else '<missing line>'
        if x != y:
            return 'stdout line %d: CPython %r / hybrid %r' % (i + 1, x[:200], y[:200])
    return None


def _run(cmd, args, stdin_path):
    stdin = open(stdin_path, 'rb') if stdin_path is not None else subprocess.DEVNULL
    try:
        return subprocess.run(cmd + args, stdin=stdin, cwd=str(REPO),
                              capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as error:
        return ('timeout', error.stdout or b'', error.stderr or b'')
    finally:
        if stdin_path is not None:
            stdin.close()


def _case(rt, task, work):
    work.mkdir(parents=True, exist_ok=True)
    return rt.make_case(task, False, work)


def _programs(rt, root):
    out = []
    for source in sorted((COMPARE / 'src').glob('*/main.py')):
        task = source.parent.name
        work = root / 'input' / task
        case = _case(rt, task, work)
        stdin_path = case['path'] if case['stdin'] else None
        out.append(dict(label='compare/%s' % task, source=source, args=list(case['args']),
                        stdin=stdin_path))
    corpus = sorted(CORPUS.glob('*/t*.py'))[:30]
    for source in corpus:
        out.append(dict(label=str(source.relative_to(REPO)), source=source, args=[], stdin=None))
    return out


def check_one(program, root, index):
    source = program['source']
    out = root / ('build-%02d' % index)
    source_text = source.read_text(encoding='utf-8')
    row = dict(program=program['label'], accelerated=[], rejected={}, match=False,
               detail='', native_names='', python_count=_top_level_count(source_text))
    try:
        report = ail_cpython_hybrid.build(source, out)
    except Exception as error:
        row['detail'] = 'hybrid build failed: %s: %s' % (type(error).__name__, error)
        return row
    row['accelerated'] = sorted(report.get('accelerated') or [])
    row['rejected'] = report.get('rejected') or {}
    row['native_names'] = ', '.join(row['accelerated']) if row['accelerated'] else '-'
    row['python_count'] = max(row['python_count'] - len(row['accelerated']), 0)
    run_file = out / report.get('run_file', source.stem + '_run.py')
    if not run_file.is_file():
        row['detail'] = 'hybrid build did not write %s' % run_file.name
        return row
    want = _run([sys.executable, '-B', str(source)], program['args'], program['stdin'])
    got = _run([sys.executable, '-B', str(run_file)], program['args'], program['stdin'])
    def fields(p):
        if isinstance(p, tuple):
            return 'timeout', p[1], p[2]
        return p.returncode, p.stdout, p.stderr
    want_rc, want_out, want_err = fields(want)
    got_rc, got_out, got_err = fields(got)
    same = (want_rc == got_rc and want_out == got_out
            and _last_line(want_err) == _last_line(got_err))
    row['match'] = same
    row['want_rc'], row['got_rc'] = want_rc, got_rc
    row['want_last_err'], row['got_last_err'] = _last_line(want_err), _last_line(got_err)
    if same:
        row['detail'] = ''
    elif want_rc != got_rc:
        row['detail'] = 'exit status: CPython %r / hybrid %r' % (want_rc, got_rc)
    else:
        row['detail'] = _first_diff(want_out, got_out) or (
            'last stderr line: CPython %r / hybrid %r'
            % (row['want_last_err'][:200], row['got_last_err'][:200]))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--keep', action='store_true', help='keep the temporary build tree')
    parser.add_argument('--tasks', action='store_true', help='only the 10 compare-lab tasks')
    parser.add_argument('--corpus', action='store_true', help='only the 30 corpus programs')
    args = parser.parse_args()
    rt = _load_run_task()
    root = Path(tempfile.mkdtemp(prefix='ail-hybrid-check-'))
    try:
        programs = _programs(rt, root)
        if args.tasks:
            programs = [p for p in programs if p['label'].startswith('compare/')]
        if args.corpus:
            programs = [p for p in programs if not p['label'].startswith('compare/')]
        rows = []
        for i, program in enumerate(programs):
            row = check_one(program, root, i)
            rows.append(row)
            print('%-40s native=%-2d match=%s %s' % (row['program'], len(row['accelerated']),
                                                     row['match'], row['detail']),
                  file=sys.stderr, flush=True)
        if args.json:
            args.json.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    finally:
        if args.keep:
            print('kept %s' % root, file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    main()
