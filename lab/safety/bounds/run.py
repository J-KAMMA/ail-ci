"""Build and classify the bounds-safety programs in four modes; write RESULTS.md.

Each program is built fresh (typed, default, general, hybrid), run under a 1.5 GB address-space
limit and a 20 second timeout, and compared with CPython 3.12 on stdout, exit status and the last
line of stderr.  No compiler file is touched: this runner only measures.
"""
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CLI = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
PYTHON = sys.executable
MODES = ('typed', 'default', 'general', 'hybrid')
CLASSES = ('match', 'stop-differs', 'silent-wrong', 'crash', 'refused')
BUILD_TIMEOUT = 600
RUN_TIMEOUT = 20
MEMORY_KB = 1_500_000


class Result:
    def __init__(self, rc, stdout, stderr, timed_out=False):
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    def last_line(self):
        text = self.stderr.decode('utf-8', 'replace')
        lines = [line for line in text.splitlines() if line.strip()]
        return lines[-1] if lines else ''

    def crashed(self):
        return self.timed_out or self.rc < 0 or self.rc >= 128


def git_output(args, fallback=''):
    try:
        return subprocess.run(['git'] + args, cwd=REPO, capture_output=True, text=True,
                              timeout=60).stdout.strip() or fallback
    except Exception:
        return fallback


def integ_commit():
    for ref in ('origin/integ', 'integ'):
        value = git_output(['rev-parse', '--short', ref])
        if value:
            return value
    root = git_output(['rev-list', '--max-parents=0', 'HEAD'])
    if root:
        return root.splitlines()[0][:7]
    return git_output(['rev-parse', '--short', 'HEAD'], 'unknown')


def build_env(mode):
    env = dict(os.environ)
    env['AIL_NO_CACHE'] = '1'
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    return env


def build_command(prog, mode, out):
    if mode == 'typed':
        return [PYTHON, '-B', str(CLI), 'compile', str(prog), '-o', str(out), '--strict']
    if mode == 'default':
        return [PYTHON, '-B', str(CLI), 'compile', str(prog), '-o', str(out)]
    if mode == 'general':
        return [PYTHON, '-B', str(CLI), 'compile', str(prog), '-o', str(out)]
    return [PYTHON, '-B', str(CLI), 'build', '--cpython', str(prog), '-o', str(out)]


def executable_for(out, prog, mode):
    if mode == 'hybrid':
        return out / prog.stem
    return out


def run_limited(command, cwd, timeout=RUN_TIMEOUT, env=None):
    wrapped = ['bash', '-c',
               f'ulimit -v {MEMORY_KB} 2>/dev/null; exec timeout {timeout} "$@"', 'bash'] + \
              [str(part) for part in command]
    started = time.monotonic()
    try:
        proc = subprocess.run(wrapped, cwd=cwd, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout + 15, env=env)
        timed_out = proc.returncode == 124 and time.monotonic() - started >= timeout
        return Result(proc.returncode, proc.stdout, proc.stderr, timed_out)
    except subprocess.TimeoutExpired as exc:
        return Result(124, exc.stdout or b'', exc.stderr or b'', True)


def build(prog, mode, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(build_command(prog, mode, out), cwd=ROOT,
                          stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=BUILD_TIMEOUT, env=build_env(mode))
    if proc.returncode != 0:
        detail = [line for line in proc.stderr.splitlines() if line.strip()]
        return 'refused', (detail[-1] if detail else f'build exited {proc.returncode}'), None
    exe = executable_for(out, prog, mode)
    if not exe.is_file():
        return 'refused', f'build exited 0 but {exe} is missing', None
    return None, '', exe


def classify(got, cpy):
    if got.crashed():
        return 'crash'
    got_stops = got.rc != 0
    cpy_stops = cpy.rc != 0
    if got_stops != cpy_stops:
        return 'silent-wrong'
    if not cpy_stops:
        if got.stdout == cpy.stdout and got.rc == cpy.rc and got.last_line() == cpy.last_line():
            return 'match'
        return 'silent-wrong'
    if got.stdout != cpy.stdout:
        return 'silent-wrong'
    if got.rc == cpy.rc and got.last_line() == cpy.last_line():
        return 'match'
    return 'stop-differs'


def repro(prog, mode):
    rel = prog.relative_to(REPO)
    out = f'/tmp/safebnd1-{prog.stem}-{mode}'
    if mode == 'typed':
        cmd = f'python3 -B AIL_CURRENT/ail_chatgpt.py compile {rel} -o {out} --strict'
    elif mode == 'general':
        cmd = f'AIL_UNIFIED_FORCE=1 python3 -B AIL_CURRENT/ail_chatgpt.py compile {rel} -o {out}'
    elif mode == 'hybrid':
        cmd = f'python3 -B AIL_CURRENT/ail_chatgpt.py build --cpython {rel} -o {out}'
    else:
        cmd = f'python3 -B AIL_CURRENT/ail_chatgpt.py compile {rel} -o {out}'
    run = f'{out}/{prog.stem}' if mode == 'hybrid' else out
    return f'`rm -rf {out} && {cmd} && (ulimit -v {MEMORY_KB}; timeout {RUN_TIMEOUT} {run})`'


def main():
    programs = sorted(ROOT.glob('p*.py'))
    if not programs:
        raise SystemExit('no p*.py programs found')
    results = {}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='safebnd1-run-') as tmp:
        work = Path(tmp)
        for prog in programs:
            cpy = run_limited([PYTHON, str(prog)], ROOT)
            results[prog.name] = {'cpython': cpy}
            for mode in MODES:
                out = work / f'{prog.stem}-{mode}'
                refused, detail, exe = build(prog, mode, out)
                if refused:
                    results[prog.name][mode] = {'class': 'refused', 'detail': detail,
                                                'got': None}
                    print(f'{prog.name} {mode}: refused', flush=True)
                    continue
                got = run_limited([str(exe)], ROOT)
                klass = classify(got, cpy)
                results[prog.name][mode] = {'class': klass, 'detail': '', 'got': got}
                print(f'{prog.name} {mode}: {klass} (rc {got.rc})', flush=True)
    elapsed = time.monotonic() - started
    write_results(programs, results, elapsed)
    counts = Counter(row[mode]['class'] for row in results.values() for mode in MODES)
    print('totals:', dict(counts), f'in {elapsed:.1f}s', flush=True)


def write_results(programs, results, elapsed):
    counts = {klass: Counter() for klass in CLASSES}
    for row in results.values():
        for mode in MODES:
            counts[row[mode]['class']][mode] += 1
    lines = []
    lines.append('# Bounds-safety results')
    lines.append('')
    lines.append(f'- Integ commit: `{integ_commit()}`')
    lines.append(f'- Date: {time.strftime("%Y-%m-%d", time.gmtime())}')
    lines.append(f'- Oracle: CPython {sys.version.split()[0]}')
    lines.append(f'- Programs: {len(programs)}; modes: {", ".join(MODES)}; '
                 f'cells: {len(programs) * len(MODES)}')
    lines.append(f'- Limits: `ulimit -v {MEMORY_KB}`, `timeout {RUN_TIMEOUT}`; '
                 f'runner wall time {elapsed:.1f}s')
    lines.append('')
    lines.append('Classification: `match` = stdout, exit status and last stderr line equal '
                 'CPython; `stop-differs` = both stop nonzero, last stderr line differs; '
                 '`silent-wrong` = one stops and the other does not, or stdout differs while '
                 'CPython stops; `crash` = signal or timeout; `refused` = build refused.')
    lines.append('')
    lines.append('| Program | typed | default | general | hybrid |')
    lines.append('| --- | --- | --- | --- | --- |')
    for prog in programs:
        row = results[prog.name]
        cells = [row[mode]['class'] for mode in MODES]
        lines.append(f'| {prog.name} | ' + ' | '.join(cells) + ' |')
    lines.append('')
    lines.append('## Totals')
    lines.append('')
    lines.append('| Class | typed | default | general | hybrid | All |')
    lines.append('| --- | --- | --- | --- | --- | --- |')
    grand = 0
    for klass in CLASSES:
        row = counts[klass]
        total = sum(row[mode] for mode in MODES)
        grand += total
        lines.append(f'| {klass} | {row["typed"]} | {row["default"]} | '
                     f'{row["general"]} | {row["hybrid"]} | {total} |')
    lines.append(f'| **All cells** | {sum(counts[k]["typed"] for k in CLASSES)} | '
                 f'{sum(counts[k]["default"] for k in CLASSES)} | '
                 f'{sum(counts[k]["general"] for k in CLASSES)} | '
                 f'{sum(counts[k]["hybrid"] for k in CLASSES)} | **{grand}** |')
    lines.append('')

    follow = []
    for prog in programs:
        row = results[prog.name]
        for mode in MODES:
            entry = row[mode]
            if entry['class'] not in ('silent-wrong', 'crash', 'stop-differs'):
                continue
            cpy = row['cpython']
            cpy_line = cpy.last_line() or '<no stderr>'
            if entry['got'] is None:
                ail = 'build refused: ' + entry['detail']
            else:
                got = entry['got']
                if got.timed_out:
                    ail = f'timeout after {RUN_TIMEOUT}s'
                elif got.crashed():
                    ail = f'killed by signal / exit {got.rc}'
                else:
                    ail = f'exit {got.rc}: ' + (got.last_line() or '<no stderr>')
                if entry['class'] == 'silent-wrong' and got.stdout != cpy.stdout:
                    ail += '; stdout differs'
            follow.append(f'- `{prog.name}` ({mode}): CPython last line {cpy_line!r}; '
                          f'AIL {ail}. Repro: {repro(prog, mode)}')
    lines.append('## Follow-ups')
    lines.append('')
    if follow:
        lines.extend(follow)
    else:
        lines.append('None: every classified cell is `match` or `refused`.')
    lines.append('')
    (ROOT / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
