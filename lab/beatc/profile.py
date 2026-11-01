#!/usr/bin/env python3
"""gprof profile of an AIL task (perf_event_open is usually denied on the runner).

    python3 lab/beatc/profile.py --tasks tree_fold term_rank --runs 4 --out /tmp/profile.json

The AIL compiler is asked to keep the generated C (--debug-dir); that C is rebuilt with
`-pg -g` and otherwise the compiler's own optimization flags, run on the task's perf input
under one pinned core, and `gprof` reports the flat function and line samples. Wall time is
only used to scale the gprof percentages; the shares themselves come from SIGPROF samples.
"""
import argparse, hashlib, importlib.util, json, os, random, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
COMPARE = REPO / 'lab' / 'compare'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
CFLAGS = ['-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
          '-fno-asynchronous-unwind-tables', '-pg', '-g', '-fno-omit-frame-pointer']


def case(task, work):
    spec = importlib.util.spec_from_file_location('gen_' + task, COMPARE / 'tasks' / task / 'gen.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _pub, _hid, perf = mod.cases(random.Random('%s-20261012' % task))
    name, data, args = perf
    path = work / 'input.bin'
    path.write_bytes(data)
    return dict(name=name, stdin=bool(getattr(mod, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args])


def _rows(text):
    """gprof flat/line tables: a numeric prefix followed by a (possibly multi-word) name."""
    rows, started, seen_rule = [], False, False
    for line in text.splitlines():
        if not started:
            if line.strip().startswith('%'):
                started = True
            continue
        if not line.strip():
            break
        if line.lstrip().startswith('Each sample'):
            continue
        parts = line.split()
        k = 0
        while k < len(parts):
            try:
                float(parts[k])
            except ValueError:
                break
            k += 1
        if k < 3 or k >= len(parts):
            continue
        name = ' '.join(parts[k:])
        rows.append(dict(pct=float(parts[0]), self_s=float(parts[2]), name=name))
    return rows


def parse_flat(text):
    return _rows(text)[:8]


def parse_lines(text):
    return _rows(text)[:12]


def profile_task(task, runs, root):
    work = root / task
    (work / 'cache').mkdir(parents=True, exist_ok=True)
    (work / 'tmp').mkdir(parents=True, exist_ok=True)
    c = case(task, work)
    # oracle
    exp = work / 'expected.out'
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        with open(exp, 'wb') as f:
            ref = subprocess.run([sys.executable, '-B', str(COMPARE / 'tasks' / task / 'reference.py'), *c['args']],
                                 stdin=stdin, stdout=f, stderr=subprocess.PIPE)
    finally:
        if c['stdin']:
            stdin.close()
    want = hashlib.sha256(exp.read_bytes()).hexdigest()
    # generated C from the AIL compiler
    dbg = work / 'dbg'
    shutil.rmtree(dbg, ignore_errors=True)
    prog = work / 'prog-ail'
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), AIL_NO_CACHE='1')
    p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(COMPARE / 'src' / task / 'main.ail'),
                        '-o', str(prog), '--debug-dir', str(dbg)], cwd=str(work), env=env, capture_output=True)
    if p.returncode != 0:
        return dict(task=task, error='AIL build failed: ' + p.stderr.decode('utf8', 'replace')[-1000:])
    pg = work / 'prog-pg'
    p = subprocess.run(['gcc', *CFLAGS, '-o', str(pg), str(dbg / 'program.c'), '-lm'], capture_output=True)
    if p.returncode != 0:
        return dict(task=task, error='pg build failed: ' + p.stderr.decode('utf8', 'replace')[-1000:])
    walls = []
    out = work / 'run.out'
    for i in range(runs):
        prefix = str(work / ('gmon-%d' % i))
        renv = dict(env, GMON_OUT_PREFIX=prefix)
        stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
        start = time.perf_counter()
        try:
            with open(out, 'wb') as f:
                rr = subprocess.run(['taskset', '-c', '0', str(pg), *c['args']], stdin=stdin, stdout=f,
                                    stderr=subprocess.PIPE, timeout=1800, env=renv, cwd=str(work))
        finally:
            if c['stdin']:
                stdin.close()
        walls.append(time.perf_counter() - start)
        if rr.returncode != 0 or hashlib.sha256(out.read_bytes()).hexdigest() != want:
            return dict(task=task, error='output mismatch/exit %d' % rr.returncode)
    out.unlink(missing_ok=True)
    gmons = sorted(str(x) for x in work.glob('gmon-*'))
    flat = subprocess.run(['gprof', '-b', '-p', str(pg), *gmons], capture_output=True, text=True).stdout
    lines = subprocess.run(['gprof', '-b', '-l', '-p', str(pg), *gmons], capture_output=True, text=True).stdout
    return dict(task=task, case=c['name'], runs=runs, wall_ms=round(1000 * sorted(walls)[len(walls) // 2], 1),
                samples_s=round(sum(r['self_s'] for r in _rows(flat)), 2), functions=parse_flat(flat),
                lines=parse_lines(lines), generated_c=str(dbg / 'program.c'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--runs', type=int, default=4)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='beatc-prof-') as tmp:
        root = Path(tmp)
        report = dict(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runs=args.runs, tasks=[])
        for task in [t for t in args.tasks.split(',') if t]:
            print('profile', task, file=sys.stderr, flush=True)
            try:
                rec = profile_task(task, args.runs, root)
            except Exception as e:
                rec = dict(task=task, error='%s: %s' % (type(e).__name__, e))
            report['tasks'].append(rec)
            Path(args.out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf8')
            print('  ', task, rec.get('error') or [(f['pct'], f['name']) for f in rec.get('functions', [])[:3]],
                  file=sys.stderr)
    print('wrote', args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
