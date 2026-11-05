"""Build every overflow program five ways, run it, and write RESULTS.md.

Each program in this directory is built typed (`--strict`), default, general
(`AIL_UNIFIED_FORCE=1`), hybrid (`build --cpython`) and exact (`--exact-int`),
run under `ulimit -v 1500000` and `timeout 20`, and compared with CPython 3.12:

  match         stdout, the exit status and the last stderr line equal CPython's
  ovf-stop      CPython prints a result, AIL exits 1 with an `OverflowError:
                integer overflow` last stderr line and prints nothing wrong first
  refused       the build refused the program
  stop-differs  both stop with a nonzero status, but the last stderr line differs
  silent-wrong  the exit status is 0 or stdout differs, and CPython stopped, or
                the other way round
  crash         killed by a signal, or the 20s timeout hit
  n/a           the hybrid build does not work on this host

`run.py` never edits a program; it only measures. Usage:

    python3 lab/safety/overflow/run.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLI = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
RESULTS = HERE / 'RESULTS.md'
MODES = ('typed', 'default', 'general', 'hybrid', 'exact')
CLASSES = ('match', 'ovf-stop', 'refused', 'stop-differs', 'silent-wrong', 'crash', 'n/a')
SAFE = ('match', 'ovf-stop')
MEM_KB = 1500000
RUN_TIMEOUT = 20
BUILD_TIMEOUT = 900
OVF_PREFIX = 'OverflowError: integer overflow'


def clean_env(extra=None):
    env = dict(os.environ)
    for key in ('AIL_UNIFIED_FORCE', 'AIL_EXACT_INT', 'AIL_BIGINT', 'AIL_NO_GENERAL',
                'AIL_UNIFIED', 'AIL_IR', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    env['AIL_NO_CACHE'] = '1'
    env.pop('PYTHONPATH', None)
    if extra:
        env.update(extra)
    return env


def limited(argv):
    """Run argv with an address-space limit and a wall-clock timeout."""
    script = 'ulimit -v %d; exec timeout %d "$@"' % (MEM_KB, RUN_TIMEOUT)
    return ['bash', '-c', script, 'overflow-limits'] + argv


def last_line(text):
    lines = text.strip().splitlines()
    return lines[-1] if lines else ''


def build(src, out, mode, workdir):
    """Build src with one mode. Returns (ok, message)."""
    name = Path(out).name
    if mode == 'typed':
        argv = [sys.executable, '-B', str(CLI), 'compile', str(src), '-o', name, '--strict']
        env = clean_env()
    elif mode == 'default':
        argv = [sys.executable, '-B', str(CLI), 'compile', str(src), '-o', name]
        env = clean_env()
    elif mode == 'general':
        argv = [sys.executable, '-B', str(CLI), 'compile', str(src), '-o', name]
        env = clean_env({'AIL_UNIFIED_FORCE': '1'})
    elif mode == 'exact':
        argv = [sys.executable, '-B', str(CLI), 'compile', str(src), '-o', name, '--exact-int']
        env = clean_env()
    elif mode == 'hybrid':
        argv = [sys.executable, '-B', str(CLI), 'build', '--cpython', str(src), '-o', name]
        env = clean_env()
    else:
        raise ValueError(mode)
    made = subprocess.run(argv, cwd=workdir, capture_output=True, text=True,
                          timeout=BUILD_TIMEOUT, env=env)
    message = (made.stdout + made.stderr).strip()
    return made.returncode == 0, message


def run_once(argv, cwd):
    """Run argv under the limits. Returns (rc, stdout, stderr, hit_timeout)."""
    try:
        done = subprocess.run(limited(argv), cwd=cwd, capture_output=True, text=True,
                              timeout=RUN_TIMEOUT + 30)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ''
        err = exc.stderr or ''
        return -9, out.decode() if isinstance(out, bytes) else out, err.decode() if isinstance(err, bytes) else err, True
    return done.returncode, done.stdout, done.stderr, done.returncode == 124


def prefix_of(stdout):
    """CPython's stdout without its final line: what a loud stop may have printed."""
    lines = stdout.splitlines(keepends=True)
    return ''.join(lines[:-1]) if lines else ''


def classify(cp, got, timed_out):
    """cp, got: (rc, stdout, stderr). Returns (class, note)."""
    cp_rc, cp_out, cp_err = cp
    rc, out, err, = got
    if timed_out or rc < 0 or rc >= 128:
        return 'crash', 'exit status %d%s' % (rc, ' (timeout)' if timed_out else '')
    if rc == cp_rc and out == cp_out and last_line(err) == last_line(cp_err):
        return 'match', ''
    if rc == 0 and cp_rc == 0:
        return 'silent-wrong', 'stdout differs (%d vs %d bytes)' % (len(out), len(cp_out))
    if rc != 0 and cp_rc != 0:
        return 'stop-differs', 'CPython: %s | AIL: %s' % (last_line(cp_err), last_line(err))
    if cp_rc == 0 and rc == 1 and out == prefix_of(cp_out) and last_line(err).startswith(OVF_PREFIX):
        return 'ovf-stop', ''
    if cp_rc == 0:
        return 'silent-wrong', 'CPython exited 0, AIL exited %d' % rc
    return 'silent-wrong', 'CPython exited %d, AIL exited 0' % cp_rc


def git_commit():
    for ref in ('origin/integ', 'HEAD'):
        done = subprocess.run(['git', 'rev-parse', '--short', ref], cwd=str(ROOT),
                              capture_output=True, text=True)
        if done.returncode == 0:
            return done.stdout.strip(), ref
    return 'unknown', 'unknown'


def build_all(programs, workroot):
    """Build and run every program in every mode. Returns ({program: CPython run}, {(program, mode): cell})."""
    cells = {}
    oracle = {}
    for program in programs:
        src = HERE / program
        cp_rc, cp_out, cp_err, cp_timeout = run_once([sys.executable, '-B', str(src)], str(HERE))
        cp = (cp_rc, cp_out, cp_err)
        oracle[program] = cp
        for mode in MODES:
            workdir = Path(tempfile.mkdtemp(prefix='ovf-%s-%s-' % (program[:-3], mode), dir=str(workroot)))
            out = workdir / ('out' if mode == 'hybrid' else 'out.bin')
            ok, message = build(src, out, mode, workdir)
            if not ok:
                if mode == 'hybrid':
                    cells[program, mode] = ('n/a', message or 'build failed', None)
                else:
                    cells[program, mode] = ('refused', message, None)
                continue
            if mode == 'hybrid':
                runner = out / program[:-3]
                if not runner.is_file():
                    cells[program, mode] = ('n/a', 'no launcher at %s' % runner, None)
                    continue
                argv = [str(runner)]
            else:
                argv = [str(out)]
            rc, stdout, stderr, timed_out = run_once(argv, str(workdir))
            cls, note = classify(cp, (rc, stdout, stderr), timed_out)
            cells[program, mode] = (cls, note, (rc, stdout, stderr))
        print(program, {m: cells[program, m][0] for m in MODES}, flush=True)
    return oracle, cells


def table(programs, cells):
    lines = ['| program | ' + ' | '.join(MODES) + ' |',
             '|---|' + '---|' * len(MODES)]
    for program in programs:
        lines.append('| `%s` | ' % program + ' | '.join(cells[program, m][0] for m in MODES) + ' |')
    return lines


def totals(programs, cells):
    lines = ['| class | ' + ' | '.join(MODES) + ' | total |',
             '|---|' + '---|' * (len(MODES) + 1)]
    grand = 0
    for cls in CLASSES:
        counts = [sum(1 for p in programs if cells[p, m][0] == cls) for m in MODES]
        grand += sum(counts)
        if not sum(counts):
            continue
        lines.append('| `%s` | ' % cls + ' | '.join(str(c) for c in counts) + ' | %d |' % sum(counts))
    lines.append('| **cells** | ' + ' | '.join(
        str(len(programs)) for m in MODES) + ' | %d |' % grand)
    return lines


def summary(programs, cells):
    def count(mode, cls):
        return sum(1 for p in programs if cells[p, mode][0] == cls)

    def column(mode):
        return '`%s`: %s' % (mode, ', '.join(
            '%d `%s`' % (count(mode, cls), cls) for cls in CLASSES if count(mode, cls)))

    misses = ['`%s`' % p for p in programs if cells[p, 'exact'][0] != 'match']
    return [
        '- unsafe cells: %d `silent-wrong`, %d `crash`, %d `stop-differs`.' % (
            sum(count(m, 'silent-wrong') for m in MODES),
            sum(count(m, 'crash') for m in MODES),
            sum(count(m, 'stop-differs') for m in MODES)),
        '- ' + '; '.join(column(m) for m in ('typed', 'default', 'general', 'hybrid')) + '.',
        '- `exact`: %d `match`, %d not `match` (%s).' % (
            count('exact', 'match'), len(misses), ', '.join(misses) or 'none'),
    ]


def one_line(text, width=600):
    flat = ' / '.join(line.strip() for line in text.strip().splitlines() if line.strip())
    flat = flat.replace(str(HERE) + os.sep, '').replace('|', '/')
    return flat[:width] + ('...' if len(flat) > width else '')


def attention(mode, cls):
    """A cell to show in the details: unsafe anywhere, or an exact cell that is not a match."""
    if cls in SAFE:
        return mode == 'exact' and cls != 'match'
    return True


def follow_up_needed(mode, cls):
    """The follow-ups the brief asks for: silent-wrong, crash, stop-differs, and any exact miss."""
    if cls in ('silent-wrong', 'crash', 'stop-differs'):
        return True
    return mode == 'exact' and cls != 'match'


def repro(program, mode):
    src = 'lab/safety/overflow/' + program
    cli = 'python3 -B AIL_CURRENT/ail_chatgpt.py'
    if mode == 'typed':
        return '`%s compile %s -o /tmp/ovf-out --strict`' % (cli, src)
    if mode == 'exact':
        return '`%s compile %s -o /tmp/ovf-out --exact-int`' % (cli, src)
    if mode == 'general':
        return '`AIL_UNIFIED_FORCE=1 %s compile %s -o /tmp/ovf-out`' % (cli, src)
    if mode == 'hybrid':
        return '`%s build --cpython %s -o /tmp/ovf-out && /tmp/ovf-out/%s`' % (cli, src, program[:-3])
    return '`%s compile %s -o /tmp/ovf-out`' % (cli, src)


def details(programs, oracle, cells):
    rows = []
    for program in programs:
        for mode in MODES:
            cls, note, got = cells[program, mode]
            if not attention(mode, cls):
                continue
            cp = oracle[program]
            cp_cell = '(exit %d, stdout %r, last stderr %r)' % (cp[0], cp[1], last_line(cp[2]))
            if got is not None:
                ail_cell = '(exit %d, stdout %r, last stderr %r)' % (got[0], got[1], last_line(got[2]))
            else:
                ail_cell = '%s: %s' % ('build failed' if cls == 'n/a' else 'build refused', one_line(note))
            rows.append('| `%s` | %s | `%s` | %s | %s |' % (program, mode, cls, cp_cell, ail_cell))
    if not rows:
        return ['None: every cell is `match` or `ovf-stop`, and every exact cell is `match`.']
    return ['| program | mode | class | CPython | AIL |',
            '|---|---|---|---|---|'] + rows


def follow_ups(programs, oracle, cells):
    entries = []
    for program in programs:
        for mode in MODES:
            cls, note, got = cells[program, mode]
            if not follow_up_needed(mode, cls):
                continue
            cp = oracle[program]
            if got is None:
                entries.append('- `%s` / %s is `%s`; the build said: %s. Repro: %s against '
                               '`python3 lab/safety/overflow/%s`.'
                               % (program, mode, cls, one_line(note), repro(program, mode), program))
                continue
            cp_rc, cp_out, cp_err = cp
            rc, out, err = got
            entries.append('- `%s` / %s is `%s`: CPython exits %d with stdout %r and last stderr %r; '
                           'AIL exits %d with stdout %r and last stderr %r. Repro: `python3 '
                           'lab/safety/overflow/%s` and %s.'
                           % (program, mode, cls, cp_rc, cp_out, last_line(cp_err), rc, out,
                              last_line(err), program, repro(program, mode)))
    return entries or ['None: no `silent-wrong`, `crash`, `stop-differs` cell and no exact-mode miss.']


def main(argv):
    if not CLI.is_file():
        print('cannot find %s' % CLI, file=sys.stderr)
        return 2
    programs = sorted(p.name for p in HERE.glob('*.py') if p.name != 'run.py')
    if len(programs) != 24:
        print('warning: %d programs, the table expects 24' % len(programs), file=sys.stderr)
    workroot = tempfile.mkdtemp(prefix='ovf-builds-')
    started = time.time()
    try:
        print('building %d programs x %d modes' % (len(programs), len(MODES)), flush=True)
        oracle, cells = build_all(programs, workroot)
    finally:
        shutil.rmtree(workroot, ignore_errors=True)
    commit, ref = git_commit()
    date = time.strftime('%Y-%m-%d')
    elapsed = time.time() - started
    classified = sum(1 for p in programs for m in MODES if cells[p, m][0] != 'n/a')
    lines = [
        '# int64 overflow safety across the builds',
        '',
        'Date: %s  ' % date,
        'Base: `%s` at `%s`  ' % (ref, commit),
        'Generator: `python3 lab/safety/overflow/run.py` (every binary under `ulimit -v %d` and `timeout %d`)  '
        % (MEM_KB, RUN_TIMEOUT),
        'Oracle: CPython %d.%d.%d from `python3 <program>.py`.' % sys.version_info[:3],
        '',
        'Ints are int64 by default and an overflow must stop loudly (owner decision 2026-10-31). '
        'A cell is `match` when stdout, the exit status and the last stderr line equal CPython\'s; '
        '`ovf-stop` when CPython prints a result and AIL exits 1 with an `OverflowError: integer overflow` '
        'last stderr line and nothing wrong on stdout first. `ovf-stop` counts as safe.',
        '',
        '%d programs, %d classified cells (%d cells `n/a`), generated in %.0fs.'
        % (len(programs), classified, len(programs) * len(MODES) - classified, elapsed),
        '',
        '## Summary',
        ''] + summary(programs, cells) + [
        '',
        '## Table',
        ''] + table(programs, cells) + [
        '',
        '## Totals',
        ''] + totals(programs, cells) + [
        '',
        '## Cells that need a follow-up',
        '',
        'Unsafe cells anywhere, plus every `exact` cell that is not `match`.',
        ''] + details(programs, oracle, cells) + [
        '',
        '## Follow-ups',
        '',
        'Each cell below is a measurement the compiler owner must decide on; this suite never fixes the compiler.',
        ''] + follow_ups(programs, oracle, cells) + ['']
    RESULTS.write_text('\n'.join(lines), encoding='utf-8')
    print('wrote %s in %.0fs' % (RESULTS, elapsed))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
