#!/usr/bin/env python3
"""Roof measurement: wall, instructions, LLC misses for each compare program (AIL and C).

    python3 lab/roof/measure.py --out lab/roof/data

For each of the ten `lab/compare/src/<task>` programs it builds the C source with gcc -O2 and the
AIL source exactly as lab/compare's run_task.py does (`compile --syntax python`), runs each binary
three times on the task's perf input (median wall), and counts instructions and cache misses.

Counters: this runner's vCPUs expose no hardware PMU (`/sys/bus/event_source/devices/` has no
`cpu`), so perf_event_open and tools/icount.c fail and the fallback is valgrind's cachegrind with
the runner's real cache geometry (L1d 32 KiB, L2 512 KiB, LLC 32 MiB). Its `I refs` is the
instruction count and `LLd misses` the LLC misses; both are simulated, not measured by hardware.
The method is written into every row.
"""
import argparse, ast, concurrent.futures, importlib.util, json, os, random, re, statistics
import subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
TASKS_SRC = REPO / 'lab' / 'compare' / 'src'
TASKS_GEN = REPO / 'lab' / 'compare' / 'tasks'
CACHEGRIND = ['valgrind', '--tool=cachegrind', '--cache-sim=yes', '--branch-sim=no',
              '--I1=32768,8,64', '--D1=32768,8,64', '--L2=524288,8,64', '--LL=33554432,16,64']
IR_ONLY = ['valgrind', '--tool=cachegrind', '--cache-sim=no', '--branch-sim=no']


def perf_available():
    """True when perf_event_open counts hardware instructions here (tools/icount.c)."""
    probe = Path(tempfile.mkdtemp()) / 'icount'
    try:
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(probe),
                        str(REPO / 'tools' / 'icount.c')], check=True, capture_output=True)
        p = subprocess.run([str(probe), '/bin/true'], capture_output=True, timeout=30)
        return p.returncode == 0 and p.stdout.strip().isdigit() and int(p.stdout) > 0
    except Exception:
        return False


def make_case(name, work):
    spec = importlib.util.spec_from_file_location('g_' + name, TASKS_GEN / name / 'gen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _pub, _hid, perf = module.cases(random.Random('%s-20261012' % name))
    case_name, data, args = perf
    path = work / (name + '.bin')
    path.write_bytes(data)
    return dict(stdin=bool(getattr(module, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], bytes=len(data))


def build(task, lang, out):
    src = TASKS_SRC / task / ('main.c' if lang == 'c' else 'typed.py')
    if lang == 'c':
        cmd = ['gcc', '-O2', '-std=c11', '-o', str(out), str(src), '-lm']
    else:
        cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python', '-o', str(out)]
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    return p.returncode == 0 and out.is_file(), p


def invocation(binary, case):
    return [str(binary)], (open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL), case['args']


def time_runs(binary, case, runs):
    walls, rc = [], None
    for _ in range(runs):
        cmd, stdin, args = invocation(binary, case)
        t0 = time.perf_counter()
        p = subprocess.run(cmd + args, stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
        walls.append(time.perf_counter() - t0)
        rc = p.returncode
        if case['stdin']:
            stdin.close()
    return statistics.median(walls), walls, rc


NUM = re.compile(r'==\d+== ([A-Za-z0-9 ]+?):\s*([\d,]+)')


def cachegrind(binary, case, out_file, timeout):
    tools = (('ir', IR_ONLY),) if os.environ.get('ROOF_IR_ONLY') else (('sim', CACHEGRIND), ('ir', IR_ONLY))
    for label, tool in tools:
        cmd, stdin, args = invocation(binary, case)
        cg = str(out_file) + '.' + label
        try:
            p = subprocess.run(tool + ['--cachegrind-out-file=' + cg] + cmd + args, stdin=stdin,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            if case['stdin']:
                stdin.close()
            return dict(icount_method='timeout', instructions=None)
        finally:
            if case['stdin']:
                stdin.close()
            Path(cg).unlink(missing_ok=True)
        counts = {' '.join(m.group(1).split()): int(m.group(2).replace(',', ''))
                  for m in NUM.finditer(p.stderr.decode('utf8', 'replace'))}
        if p.returncode == 0 and 'I refs' in counts:
            rec = dict(icount_method='callgrind-' + label, instructions=counts.get('I refs'),
                       d_refs=counts.get('D refs'), d1_misses=counts.get('D1 misses'),
                       ll_misses=counts.get('LL misses'), lld_misses=counts.get('LLd misses'))
            if label == 'sim':
                return rec
            return rec
    return dict(icount_method='failed', instructions=None)


def one_task(task, work, runs, timeout, want_cache):
    case = make_case(task, work)
    row = dict(task=task, input_bytes=case['bytes'])
    bins = {}
    for lang in ('c', 'ail'):
        out = work / ('%s_%s' % (task, lang))
        ok, p = build(task, lang, out)
        row[lang + '_build_ok'] = ok
        if not ok:
            row[lang + '_build_error'] = p.stderr.decode('utf8', 'replace')[-400:]
        bins[lang] = out
        if lang == 'ail' and ok:
            strict = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(TASKS_SRC / task / 'typed.py'),
                                     '--syntax', 'python', '--strict', '-o', str(work / ('%s_strict' % task))],
                                    capture_output=True, timeout=1800)
            row['ail_path'] = 'typed' if strict.returncode == 0 else 'general'
            if strict.returncode != 0:
                lines = strict.stderr.decode('utf8', 'replace').splitlines()
                for i, line in enumerate(lines):
                    if 'why not typed' in line:
                        row['ail_why_not_typed'] = ((lines[i - 1] if i else '') + ' | ' + line).strip()[:300]
                        break
    for lang in ('c', 'ail'):
        if not row.get(lang + '_build_ok'):
            continue
        wall, walls, rc = time_runs(bins[lang], case, runs)
        row[lang + '_wall_s'] = round(wall, 4)
        row[lang + '_wall_runs'] = [round(w, 4) for w in walls]
        row[lang + '_rc'] = rc
        if want_cache:
            row[lang] = cachegrind(bins[lang], case, work / ('%s_%s.cg' % (task, lang)), timeout)
        else:
            row[lang] = dict(icount_method='skipped', instructions=None)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'data'))
    ap.add_argument('--tasks', default='berth_sim,chain_relax,echo_pack,ledger_bin,rail_transfer,scar_life,'
                                       'tally_lang,term_rank,ticket_audit,tree_fold')
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--cache-timeout', type=int, default=1200)
    ap.add_argument('--no-cache', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in args.tasks.split(',') if t]
    print('hardware PMU (perf_event_open instructions):', 'yes' if perf_available() else 'no -> valgrind cachegrind',
          flush=True)
    with tempfile.TemporaryDirectory(prefix='roof-') as tmp:
        work = Path(tmp)
        rows = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(one_task, t, work, args.runs, args.cache_timeout, not args.no_cache): t for t in tasks}
            for fut in concurrent.futures.as_completed(futs):
                t = futs[fut]
                try:
                    rows[t] = fut.result()
                except Exception as e:
                    rows[t] = dict(task=t, error='%s: %s' % (type(e).__name__, e))
                (out / 'programs.json').write_text(json.dumps(rows, indent=1) + '\n')
                print('done', t, flush=True)
    (out / 'programs.json').write_text(json.dumps(rows, indent=1) + '\n')
    cols = ['task', 'lang', 'wall_s', 'instructions', 'llc_misses', 'd1_misses', 'icount_method', 'path']
    print('\t'.join(cols))
    for t in tasks:
        r = rows.get(t, {})
        for lang in ('ail', 'c'):
            sub = r.get(lang) or {}
            print('\t'.join(str(x) for x in [t, lang, r.get(lang + '_wall_s'), sub.get('instructions'),
                                             sub.get('lld_misses'), sub.get('d1_misses'), sub.get('icount_method'),
                                             r.get('ail_path', '') if lang == 'ail' else '']))


if __name__ == '__main__':
    main()
