#!/usr/bin/env python3
"""splitlab.py -- lab only: what would compiling the runtime once (and only the program per build) cost and save?

    splitlab.py --out DIR [--n 24] [--ail AIL_CURRENT/ail_chatgpt.py] [--variants none,40,12] [--icount PATH]

For N corpus programs (lab/corpus/programs, an even stride) it builds the program the normal way to get the generated C and the
reference executable, then for each variant of split.py (which functions leave the program unit):

  full    one `gcc` call on program.c: compile + link, exactly the flags of the build        (what a build costs today)
  rt      gcc -c on rt.c                                                                      (paid once, then cached)
  user    gcc -c on user.c, plus the link of user.o + rt.o                                    (what a build would cost)

CPU time (user+sys of the gcc process tree, median of 3) is the number; wall time is recorded too.  Every variant's executable
is run on the task's inputs: stdout and exit code must equal the reference, and the user-space instruction count (icount, or
valgrind's I refs when perf_event_open is not allowed) must not be higher.  Output: DIR/split.jsonl and DIR/split.md.
"""
import argparse, glob, hashlib, json, os, re, resource, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1] if (HERE.parents[1] / 'AIL_CURRENT').exists() else HERE.parent
FLAGS = ['-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd', '-fno-asynchronous-unwind-tables',
         '-ffunction-sections', '-fdata-sections']
LINK = ['-Wl,--gc-sections']


def cpu_run(cmd, **kw):
    """-> (returncode, cpu seconds of the child tree, wall seconds, stderr)"""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    wall = time.time() - t
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    return p.returncode, cpu, wall, p.stderr


def med(xs):
    return statistics.median(xs)


def timed(cmd, n=3):
    cpus, walls = [], []
    for _ in range(n):
        rc, cpu, wall, err = cpu_run(cmd)
        if rc:
            return None, None, err[-600:]
        cpus.append(cpu)
        walls.append(wall)
    return med(cpus), med(walls), ''


class Counter:
    def __init__(self, path):
        self.path = path
        self.mode = None
        if path and os.path.exists(path):
            p = subprocess.run([path, '/bin/true'], capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip().isdigit():
                self.mode = 'icount'
        if not self.mode and shutil.which('valgrind'):
            self.mode = 'valgrind'

    def count(self, exe, data):
        if self.mode == 'icount':
            p = subprocess.run([self.path, exe], input=data, capture_output=True, timeout=300)
            try:
                return int(p.stdout.decode().strip().splitlines()[-1])
            except Exception:
                return None
        if self.mode == 'valgrind':
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, 'cg.out')
                p = subprocess.run(['valgrind', '--tool=cachegrind', '--cache-sim=no', '--cachegrind-out-file=' + out, exe],
                                   input=data, capture_output=True, timeout=900)
                m = re.search(rb'I\s+refs:\s+([\d,]+)', p.stderr)
                return int(m.group(1).replace(b',', b'')) if m else None
        return None


def run_exe(exe, data):
    p = subprocess.run([exe], input=data, capture_output=True, timeout=60)
    return hashlib.sha256(p.stdout).hexdigest()[:12], p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--ail', default=str(REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'))
    ap.add_argument('--variants', default='none,40,12')
    ap.add_argument('--icount', default='/tmp/icount')
    ap.add_argument('--shard', type=int, default=0)
    ap.add_argument('--of', type=int, default=1)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    split = str(HERE / 'split.py')
    corpus = REPO / 'lab' / 'corpus'
    progs = sorted(glob.glob(str(corpus / 'programs' / '*' / 't*.py')))
    stride = max(1, len(progs) // a.n)
    progs = progs[::stride][:a.n][a.shard::a.of]
    variants = a.variants.split(',')
    counter = Counter(a.icount)
    print('counter:', counter.mode, flush=True)
    rows = []
    rt_hashes = {v: {} for v in variants}
    for pth in progs:
        model = Path(pth).parent.name
        tid = Path(pth).stem
        label = '%s/%s' % (model.split('-')[0], tid)
        work = Path(tempfile.mkdtemp(prefix='sl-'))
        env = dict(os.environ, AIL_NO_CACHE='1', PYTHONHASHSEED='0', AIL_QUIET_FALLBACK='1')
        ref = work / 'ref.bin'
        p = subprocess.run([sys.executable, '-B', a.ail, 'compile', pth, '--syntax', 'python', '-o', str(ref),
                            '--debug-dir', str(work / 'dbg')], capture_output=True, text=True, env=env, timeout=600)
        if p.returncode:
            rows.append(dict(label=label, status='refused'))
            shutil.rmtree(work, ignore_errors=True)
            continue
        c = work / 'dbg' / 'program.c'
        text = c.read_text(encoding='utf-8')
        if 'interned attribute-name ids' not in text:
            rows.append(dict(label=label, status='typed', c_bytes=len(text)))
            shutil.rmtree(work, ignore_errors=True)
            continue
        row = dict(label=label, status='ok', c_bytes=len(text))
        full = work / 'full'
        cpu, wall, err = timed(['gcc', *FLAGS, *LINK, '-o', str(full), str(c), '-lm'])
        if cpu is None:
            rows.append(dict(label=label, status='full failed: ' + err))
            shutil.rmtree(work, ignore_errors=True)
            continue
        row['full_cpu'], row['full_wall'], row['full_bytes'] = cpu, wall, full.stat().st_size
        inputs = []
        for k in range(3):
            f = corpus / 'tasks' / tid / ('in%d.txt' % k)
            if f.exists():
                inputs.append(f.read_bytes())
        ref_out = [run_exe(str(ref), d) for d in inputs]
        row['ref_same_as_full'] = [run_exe(str(full), d) for d in inputs] == ref_out
        row['full_icount'] = [counter.count(str(full), d) for d in inputs]
        row['variants'] = {}
        for v in variants:
            vd = work / ('v_' + v)
            args = [sys.executable, split, str(c), str(vd)] + ([] if v == 'none' else ['--inline-lines', v])
            q = subprocess.run(args, capture_output=True, text=True)
            if q.returncode:
                row['variants'][v] = dict(status='split failed: ' + q.stderr[-300:])
                continue
            rt_text = (vd / 'rt.c').read_bytes()
            rt_hashes[v].setdefault(hashlib.sha256(rt_text).hexdigest()[:10], []).append(label)
            res = dict(moved=q.stdout.strip())
            cpu, wall, err = timed(['gcc', *FLAGS, '-w', '-c', str(vd / 'rt.c'), '-o', str(vd / 'rt.o')], 1)
            if cpu is None:
                res['status'] = 'rt failed: ' + err
                row['variants'][v] = res
                continue
            res['rt_cpu'] = cpu
            cpu, wall, err = timed(['gcc', *FLAGS, '-w', '-c', str(vd / 'user.c'), '-o', str(vd / 'user.o')])
            if cpu is None:
                res['status'] = 'user failed: ' + err
                row['variants'][v] = res
                continue
            res['user_cpu'], res['user_wall'] = cpu, wall
            lcpu, lwall, err = timed(['gcc', *FLAGS, *LINK, str(vd / 'user.o'), str(vd / 'rt.o'), '-o', str(vd / 'prog'), '-lm'])
            if lcpu is None:
                res['status'] = 'link failed: ' + err
                row['variants'][v] = res
                continue
            res['link_cpu'] = lcpu
            res['build_cpu'] = res['user_cpu'] + lcpu
            res['bytes'] = (vd / 'prog').stat().st_size
            res['same_output'] = [run_exe(str(vd / 'prog'), d) for d in inputs] == ref_out
            res['icount'] = [counter.count(str(vd / 'prog'), d) for d in inputs]
            res['status'] = 'ok'
            row['variants'][v] = res
        rows.append(row)
        print(label, {v: (r.get('build_cpu'), r.get('same_output')) for v, r in row['variants'].items()}, 'full', row['full_cpu'],
              flush=True)
        shutil.rmtree(work, ignore_errors=True)
    with open(out / 'split.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    with open(out / 'rt_hashes.json', 'w') as f:
        json.dump({v: {h: l for h, l in d.items()} for v, d in rt_hashes.items()}, f)
    report([out / 'split.jsonl'], out / 'split.md', variants, counter.mode, rt_hashes)


def report(files, dest, variants, mode, rt_hashes=None):
    rows = []
    for fp in files:
        rows += [json.loads(l) for l in open(fp) if l.strip()]
    ok = [r for r in rows if r.get('status') == 'ok']
    L = ['# AIL runtime split lab', '',
         '%d programs: %d general path (measured), %d typed path (no runtime prelude to split), %d refused. Instruction counter: %s.'
         % (len(rows), len(ok), sum(r.get('status') == 'typed' for r in rows), sum(r.get('status') == 'refused' for r in rows), mode),
         '', 'CPU seconds of the gcc process tree, median of 3 (`rt` once). `build` = user.c compile + link; `full` = one call, as the build does today.', '']
    for v in variants:
        good = [r for r in ok if r['variants'].get(v, {}).get('status') == 'ok']
        if not good:
            continue
        name = 'only non-inline `static` functions move' if v == 'none' else 'non-inline plus `static inline` functions longer than %s lines move' % v
        L += ['## variant %s: %s' % (v, name), '', '| program | C KB | full s | rt s (once) | build s | saved | exe KB full/split | output same | icount full -> split |',
              '|---|---|---|---|---|---|---|---|---|']
        sv, losses = [], 0
        for r in good:
            x = r['variants'][v]
            saved = 1 - x['build_cpu'] / r['full_cpu']
            sv.append(saved)
            ic = ['%s -> %s' % (a_, b_) for a_, b_ in zip(r['full_icount'], x['icount'])]
            worse = any(a_ is not None and b_ is not None and b_ > a_ for a_, b_ in zip(r['full_icount'], x['icount']))
            losses += worse
            L.append('| %s | %d | %.2f | %.2f | %.2f | %.0f%% | %d/%d | %s | %s%s |' % (
                r['label'], r['c_bytes'] // 1000, r['full_cpu'], x['rt_cpu'], x['build_cpu'], 100 * saved, r['full_bytes'] // 1000,
                x['bytes'] // 1000, 'yes' if x['same_output'] else '**NO**', '; '.join(ic), ' **loss**' if worse else ''))
        tot_full = sum(r['full_cpu'] for r in good)
        tot_build = sum(r['variants'][v]['build_cpu'] for r in good)
        L += ['', 'Pooled gcc CPU: full %.1f s -> build %.1f s = **%.0f%% saved** (median per program %.0f%%, min %.0f%%). '
              'Programs whose instruction count rose on some input: **%d of %d**.' % (
                  tot_full, tot_build, 100 * (1 - tot_build / tot_full), 100 * statistics.median(sv), 100 * min(sv), losses, len(good)), '']
        if rt_hashes and rt_hashes.get(v):
            L += ['Distinct runtime texts over the %d programs: %d.' % (sum(len(l) for l in rt_hashes[v].values()), len(rt_hashes[v])), '']
    dest.write_text('\n'.join(L) + '\n')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'report':
        report([Path(p) for p in sys.argv[4:]], Path(sys.argv[2]), sys.argv[3].split(','), 'merged')
    else:
        main()
