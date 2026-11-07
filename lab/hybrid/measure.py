#!/usr/bin/env python3
"""Numbers for the hybrid report: wall time, instruction counts, and program.c stability.

    python3 lab/hybrid/measure.py [--json /tmp/hybrid-numbers.json] [--runs 5] [--base /tmp/base]

For the 10 compare-lab tasks this measures wall time (median of `--runs`) for CPython, the hybrid,
and the standalone binary from `ail_chatgpt.py compile`.  It then builds the standalone binary with
`--debug-dir` from this checkout and from `origin/integ`, and byte-compares `program.c`.
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT'
COMPARE = REPO / 'lab' / 'compare'
EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')
RUN_TIMEOUT = 1500


def load_run_task():
    import importlib.util
    spec = importlib.util.spec_from_file_location('ail_compare_run_task', COMPARE / 'run_task.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_hybrid():
    sys.path.insert(0, str(AIL))
    import ail_cpython_hybrid
    return ail_cpython_hybrid


def run_once(cmd, args, stdin_path, stdout=subprocess.DEVNULL, timeout=RUN_TIMEOUT):
    stdin = open(stdin_path, 'rb') if stdin_path is not None else subprocess.DEVNULL
    start = time.perf_counter()
    try:
        p = subprocess.run(cmd + args, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                           cwd=str(REPO), timeout=timeout)
        return p.returncode, time.perf_counter() - start, p.stderr or b''
    finally:
        if stdin_path is not None:
            stdin.close()


def compile_cmd(compiler, source, out, debug=None, exact=False):
    cmd = [sys.executable, '-B', str(compiler), 'compile', str(source), '--syntax', 'python']
    if exact:
        cmd.append('--exact-int')
    cmd.extend(['-o', str(out)])
    if debug is not None:
        cmd.extend(['--debug-dir', str(debug)])
    return cmd


def build_standalone(compiler, source, out, debug=None, exact=False):
    out.unlink(missing_ok=True)
    p = subprocess.run(compile_cmd(compiler, source, out, debug, exact),
                       capture_output=True, text=True, cwd=str(REPO),
                       env=dict(os.environ, AIL_NO_CACHE='1'), timeout=1800)
    if p.returncode != 0 or not out.is_file():
        raise BuildRefused(_refusal(p.stderr or p.stdout or ''))
    return out


class BuildRefused(RuntimeError):
    pass


def _refusal(text):
    """The first line of a compiler or run failure, path-normalised so two trees can be compared."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith('note:') or line.startswith('write instead:'):
            continue
        return ' '.join(line.split())[:400]
    return (lines[0][:400] if lines else 'unknown refusal')


def icount_tool(work):
    exe = work / 'icount'
    try:
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h',
                        '-o', str(exe), str(REPO / 'tools' / 'icount.c')],
                       check=True, capture_output=True)
        p = subprocess.run([str(exe), '/bin/true'], capture_output=True, timeout=30)
        if p.returncode == 0 and p.stdout.strip().isdigit() and int(p.stdout) > 0:
            return exe, None
        return None, 'icount self-test exit %d: %s' % (p.returncode,
                                                       p.stderr.decode('utf-8', 'replace')[-300:])
    except Exception as error:
        return None, '%s: %s' % (type(error).__name__, error)


def count_instructions(icount, cmd, args, stdin_path, work, label):
    out = work / ('icount-' + label)
    try:
        with open(out, 'wb') as handle:
            p = run_once([str(icount)], cmd + args, stdin_path, stdout=handle)
        text = out.read_text(errors='replace').split()
        return int(text[-1]) if p[0] == 0 and text and text[-1].lstrip('-').isdigit() else None
    except Exception:
        return None
    finally:
        out.unlink(missing_ok=True)


def program_c(task, source, compiler, work, label, exact):
    """(program.c bytes, refusal) for one tree; the refusal is None when the build succeeded."""
    out = work / ('standalone-' + label)
    debug = work / ('debug-' + label)
    if debug.exists():
        shutil.rmtree(debug)
    try:
        build_standalone(compiler, source, out, debug, exact)
    except BuildRefused as error:
        return None, str(error)
    path = debug / 'program.c'
    return (path.read_bytes() if path.is_file() else None), None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--base', type=Path, default=Path('/tmp/base-cpyhyb2b'))
    parser.add_argument('--only', choices=('all', 'time', 'compare'), default='all')
    args = parser.parse_args()
    rt = load_run_task()
    hybrid = load_hybrid()
    work = Path(tempfile.mkdtemp(prefix='ail-hybrid-numbers-'))
    rows, compare, icount, icount_error = [], [], None, None
    if args.json and args.json.is_file():
        try:
            old = json.loads(args.json.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            old = {}
        rows = old.get('rows') or []
        compare = old.get('program_c') or []
        icount = old.get('icount_available') or None
        icount_error = old.get('icount_error')
    done_rows = {row['task'] for row in rows}
    done_compare = {row['task'] for row in compare}

    def save():
        data = dict(runs=args.runs, icount_available=bool(icount), icount_error=icount_error,
                    rows=rows, program_c=compare)
        if args.json:
            args.json.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

    try:
        if args.only in ('all', 'time'):
            icount, icount_error = icount_tool(work)
            tasks = [d.name for d in sorted((COMPARE / 'src').iterdir())
                     if (d / 'main.py').is_file()]
            for task in tasks:
                if task in done_rows:
                    continue
                source = COMPARE / 'src' / task / 'main.py'
                exact = task in EXACT_INT_TASKS
                task_work = work / task
                task_work.mkdir()
                case = rt.make_case(task, False, task_work)
                stdin_path = case['path'] if case['stdin'] else None
                argv = list(case['args'])
                hybrid_out = task_work / 'hybrid'
                report = hybrid.build(source, hybrid_out)
                hybrid_run = hybrid_out / report['run_file']
                try:
                    standalone = build_standalone(AIL / 'ail_chatgpt.py', source,
                                                  task_work / 'standalone', exact=exact)
                except BuildRefused as error:
                    standalone = None
                    standalone_note = 'compile refused: %s' % error
                else:
                    standalone_note = None
                modes = {
                    'python': [sys.executable, '-B', str(source)],
                    'hybrid': [sys.executable, '-B', str(hybrid_run)],
                }
                if standalone is not None:
                    modes['standalone'] = [str(standalone)]
                walls, counts, notes = {}, {}, {}
                if standalone_note:
                    walls['standalone'] = None
                    notes['standalone'] = standalone_note
                for name, cmd in modes.items():
                    times = []
                    for _ in range(args.runs):
                        rc, elapsed, err = run_once(cmd, argv, stdin_path)
                        if rc != 0:
                            notes[name] = 'exit %d: %s' % (rc, _refusal(err))
                            times = []
                            break
                        times.append(elapsed)
                    walls[name] = (round(statistics.median(times) * 1000, 1) if times else None)
                    counts[name] = (count_instructions(icount, cmd, argv, stdin_path, task_work,
                                                       '%s-%s' % (task, name))
                                    if icount and times else None)
                rows.append(dict(task=task, native=report.get('accelerated') or [],
                                 wall_ms=walls, instructions=counts, notes=notes))
                save()
                def ms(value):
                    return '%8.1f' % value if value is not None else '   n/a  '
                print('%-14s python=%s hybrid=%s standalone=%s ms'
                      % (task, ms(walls['python']), ms(walls['hybrid']),
                         ms(walls['standalone'])), file=sys.stderr, flush=True)
                if notes:
                    print('  standalone unavailable: %s' % '; '.join(
                        '%s %s' % (k, v) for k, v in notes.items()),
                        file=sys.stderr, flush=True)

        if args.only in ('all', 'compare'):
            base = args.base
            integ = subprocess.run(['git', 'rev-parse', 'origin/integ'], cwd=str(REPO),
                                   capture_output=True, text=True, check=True).stdout.strip()
            at_integ = False
            if (base / 'AIL_CURRENT' / 'ail_chatgpt.py').is_file():
                head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(base),
                                      capture_output=True, text=True).stdout.strip()
                at_integ = head == integ
                if not at_integ:
                    raise RuntimeError('%s is not origin/integ (%s != %s); pass --base'
                                       % (base, head[:12], integ[:12]))
            else:
                subprocess.run(['git', 'worktree', 'add', '--detach', str(base), 'origin/integ'],
                               cwd=str(REPO), check=True, capture_output=True, text=True)
                at_integ = True
            if not at_integ:
                raise RuntimeError('base worktree is not at origin/integ')
            tasks = [d.name for d in sorted((COMPARE / 'src').iterdir())
                     if (d / 'main.py').is_file()]
            for task in tasks:
                if task in done_compare:
                    continue
                source = COMPARE / 'src' / task / 'main.py'
                exact = task in EXACT_INT_TASKS
                task_work = work / task
                task_work.mkdir(exist_ok=True)
                head, head_err = program_c(task, source, AIL / 'ail_chatgpt.py',
                                           task_work, 'head', exact)
                old, old_err = program_c(task, source, base / 'AIL_CURRENT' / 'ail_chatgpt.py',
                                         task_work, 'base', exact)
                refused = (head is None and old is None and head_err is not None
                           and head_err == old_err)
                same = (head is not None and head == old) or refused
                compare.append(dict(task=task, same=same, refused=refused,
                                    head_sha=_sha(head), base_sha=_sha(old),
                                    refusal=head_err if refused else None))
                save()
                print('program.c %-14s %s' % (task, 'identical (both refuse: %s)' % head_err
                                             if refused else
                                             ('identical' if same else 'DIFFERENT')),
                      file=sys.stderr, flush=True)
        save()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()[:16] if data is not None else None


if __name__ == '__main__':
    main()
