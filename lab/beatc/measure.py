#!/usr/bin/env python3
"""Beat-C baseline: build each lab/compare task as AIL (default) and C, then measure.

    python3 lab/beatc/measure.py --out /tmp/beatc.json
    python3 lab/beatc/measure.py --tasks tree_fold scar_life --runs 5 --out /tmp/beatc.json

For each task it writes one JSON record: build status, wall time on one core and on all
cores (median of N runs, plus every run and the spread), peak RSS, and an instruction count
from tools/icount.c when perf_event_open is permitted.

The task sources, input generator and CPython oracle are reused from lab/compare; nothing
here changes the compiler or its default output.
"""
import argparse, hashlib, importlib.util, json, os, random, re, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
COMPARE = REPO / 'lab' / 'compare'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
AIL_CFLAGS = ['-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
              '-fno-asynchronous-unwind-tables']
C_CFLAGS = ['-O2', '-std=c11']


def generator(task):
    spec = importlib.util.spec_from_file_location('gen_' + task, COMPARE / 'tasks' / task / 'gen.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_case(task, work):
    mod = generator(task)
    _pub, _hid, perf = mod.cases(random.Random('%s-20261012' % task))
    name, data, args = perf
    path = work / 'input.bin'
    path.write_bytes(data)
    return dict(name=name, stdin=bool(getattr(mod, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], input_bytes=len(data),
                task_source=COMPARE / 'src' / task)


def reference_output(task, case, work):
    out = work / 'expected.out'
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        with open(out, 'wb') as f:
            p = subprocess.run([sys.executable, '-B', str(COMPARE / 'tasks' / task / 'reference.py'), *case['args']],
                               stdin=stdin, stdout=f, stderr=subprocess.PIPE)
    finally:
        if case['stdin']:
            stdin.close()
    return dict(returncode=p.returncode, sha256=hashlib.sha256(out.read_bytes()).hexdigest(), bytes=out.stat().st_size), out


def build_ail(task, work):
    out = work / 'prog-ail'
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None); env.pop('PYTHONDONTWRITEBYTECODE', None)
    dbg = work / 'dbg'
    shutil.rmtree(dbg, ignore_errors=True)
    cmd = [sys.executable, '-B', str(AIL), 'compile', str(COMPARE / 'src' / task / 'main.ail'), '-o', str(out),
           '--debug-dir', str(dbg)]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(work), env=env, capture_output=True)
    return dict(ok=p.returncode == 0 and out.is_file(), seconds=round(time.perf_counter() - t0, 3),
                cmd=cmd, stderr=p.stderr.decode('utf8', 'replace')[-2000:], binary=out,
                generated=dbg / 'program.c')


def build_c(task, work):
    src = COMPARE / 'src' / task / 'main.c'
    out = work / 'prog-c'
    p = subprocess.run(['gcc', *C_CFLAGS, '-o', str(out), str(src), '-lm'], capture_output=True)
    return dict(ok=p.returncode == 0 and out.is_file(), binary=out,
                stderr=p.stderr.decode('utf8', 'replace')[-2000:])


def rss_from(path):
    try:
        m = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', Path(path).read_text(errors='replace'))
        return int(m.group(1)) if m else None
    except OSError:
        return None


def run_once(cmd, case, affinity, work, label):
    out, tfile = work / ('run-' + label + '.out'), work / ('time-' + label)
    prefix = ['/usr/bin/time', '-v', '-o', str(tfile), '--', 'taskset', '-c', affinity]
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    start = time.perf_counter()
    try:
        with open(out, 'wb') as f:
            p = subprocess.run([*prefix, *cmd, *case['args']], stdin=stdin, stdout=f,
                               stderr=subprocess.PIPE, timeout=1800)
    finally:
        if case['stdin']:
            stdin.close()
    elapsed = time.perf_counter() - start
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.unlink(missing_ok=True)
    return dict(seconds=elapsed, returncode=p.returncode, sha256=digest, rss_kib=rss_from(tfile))


def summarize(runs):
    walls = sorted(r['seconds'] for r in runs)
    med = statistics.median(walls)
    return dict(runs=len(walls), wall_ms=round(med * 1000, 1), min_ms=round(walls[0] * 1000, 1),
                max_ms=round(walls[-1] * 1000, 1), spread_ms=round((walls[-1] - walls[0]) * 1000, 1),
                all_ms=[round(w * 1000, 1) for w in walls],
                rss_kib=int(statistics.median([r['rss_kib'] for r in runs if r['rss_kib']])),
                returncodes=sorted(set(r['returncode'] for r in runs)),
                sha256=sorted(set(r['sha256'] for r in runs)))


def build_icount(work):
    exe = work / 'icount'
    try:
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h',
                        '-o', str(exe), str(REPO / 'tools' / 'icount.c')], check=True, capture_output=True)
        p = subprocess.run([str(exe), '/bin/true'], capture_output=True, timeout=30)
        if p.returncode == 0 and p.stdout.strip().isdigit() and int(p.stdout) > 0:
            return exe, None
        return None, (p.stderr.decode('utf8', 'replace').strip() or 'no counter')
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, e)


def icount(exe, cmd, case, work, label):
    if not exe:
        return None
    out = work / ('ic-' + label + '.out')
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        with open(out, 'wb') as f:
            p = subprocess.run([str(exe), *cmd, *case['args']], stdin=stdin, stdout=f,
                               stderr=subprocess.PIPE, timeout=1800)
        text = out.read_text(errors='replace').split() if out.exists() else []
        return int(text[-1]) if p.returncode == 0 and text and text[-1].isdigit() else None
    finally:
        if case['stdin']:
            stdin.close()
        out.unlink(missing_ok=True)


def measure_task(task, runs, work_root, icount_exe):
    work = work_root / task
    for sub in ('cache', 'tmp'):
        (work / sub).mkdir(parents=True, exist_ok=True)
    case = make_case(task, work)
    expected, expected_path = reference_output(task, case, work)
    builds = {'ail': build_ail(task, work), 'c': build_c(task, work)}
    rec = dict(task=task, case=case['name'], input_bytes=case['input_bytes'], expected=expected,
               builds={k: {kk: (str(vv) if kk in ('binary', 'generated') else vv) for kk, vv in v.items()}
                       for k, v in builds.items()})
    for lang, b in builds.items():
        if not b['ok']:
            rec['error'] = '%s build failed' % lang
            return rec
    for lang, b in builds.items():
        cmd = [str(b['binary'])]
        rec[lang] = {}
        for affinity, key in (('0', 'one_core'), ('0-3', 'all_cores')):
            rs = [run_once(cmd, case, affinity, work, '%s-%s' % (lang, key)) for _ in range(runs)]
            rec[lang][key] = summarize(rs)
        rec[lang]['instructions'] = icount(icount_exe, cmd, case, work, lang) if icount_exe else None
    rec['correct'] = all(rec[l]['one_core']['sha256'] == [expected['sha256']] and
                         rec[l]['one_core']['returncodes'] == [expected['returncode']] for l in ('ail', 'c'))
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', choices=['ail', 'c'], help='build/run only one language (debug aid)')
    args = ap.parse_args()
    tasks = [t for t in args.tasks.split(',') if t]
    with tempfile.TemporaryDirectory(prefix='beatc-') as tmp:
        root = Path(tmp)
        icount_exe, icount_note = build_icount(root)
        report = dict(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), head=subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            runs=args.runs, cpus=os.cpu_count(), icount='tools/icount.c available' if icount_exe else 'unavailable: ' + str(icount_note),
            tasks=[])
        for task in tasks:
            print('task', task, file=sys.stderr, flush=True)
            try:
                rec = measure_task(task, args.runs, root, icount_exe)
            except Exception as e:
                rec = dict(task=task, error='%s: %s' % (type(e).__name__, e))
            report['tasks'].append(rec)
            print('  ', task, {l: {k: rec.get(l, {}).get(k) for k in ('one_core', 'all_cores', 'instructions')}
                               for l in ('ail', 'c')}, file=sys.stderr)
            Path(args.out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf8')
    print('wrote', args.out, file=sys.stderr)


if __name__ == '__main__':
    main()
