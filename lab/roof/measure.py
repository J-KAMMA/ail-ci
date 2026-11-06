#!/usr/bin/env python3
"""Roof measurement: wall, instructions, LLC misses for each compare program (AIL and C).

    python3 lab/roof/measure.py --out lab/roof/data --langs ail,ail-py,c

For each of the ten `lab/compare/src/<task>` programs it builds the C source with gcc -O2 and both
AIL sources compare-lab reports: `typed.py` (compare-lab column `ail`, the annotated source) and
`main.py` (compare-lab column `ail-py`, the plain CPython source the task names). Both are built
with `compile --syntax python`, and `main.py` gets `--exact-int` for the two tasks that need big
ints (`rail_transfer`, `chain_relax`), exactly as run_task.py does. Each binary runs three times on
the task's perf input (median wall), and instructions and cache misses are counted.

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
# compare-lab's two AIL columns: `ail` builds the annotated typed.py, `ail-py` builds main.py.
SOURCE = {'c': 'main.c', 'ail': 'typed.py', 'ail-py': 'main.py'}
LANGS = ['ail', 'ail-py', 'c']
# These programs use big ints by design (a `1 << 200` sentinel, a 64-bit modular LCG); compare-lab
# passes --exact-int for their main.py build, so the roof harness must too or the build is refused.
EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')
BUILD_DIRECTIVE = re.compile(r'^#\s*ail-build:\s*(.*)$')


def wants_exact_int(task, src):
    """--exact-int when compare-lab names it or the source's `# ail-build:` line asks for it."""
    if task in EXACT_INT_TASKS:
        return True
    try:
        with open(src, encoding='utf8', errors='replace') as fh:
            for _ in range(3):
                m = BUILD_DIRECTIVE.match(fh.readline())
                if m:
                    return '--exact-int' in m.group(1)
    except OSError:
        pass
    return False


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


def build_cmd(task, lang, src, out, strict=False):
    if lang == 'c':
        return ['gcc', '-O2', '-std=c11', '-o', str(out), str(src), '-lm']
    cmd = [sys.executable, '-B', str(AIL), 'compile', str(src), '--syntax', 'python']
    if lang == 'ail-py' and wants_exact_int(task, src):
        cmd.append('--exact-int')
    if strict:
        cmd.append('--strict')
    return cmd + ['-o', str(out)]


def build(task, lang, out, strict=False):
    src = TASKS_SRC / task / SOURCE[lang]
    p = subprocess.run(build_cmd(task, lang, src, out, strict), capture_output=True, timeout=1800)
    return p.returncode == 0 and out.is_file(), p


def invocation(binary, case):
    return [str(binary)], (open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL), case['args']


TIME_BIN = '/usr/bin/time' if Path('/usr/bin/time').is_file() else None
CPUTIME = re.compile(rb'ROOFCPU ([\d.]+) ([\d.]+) ([\d.]+)')


def time_runs(binary, case, runs):
    walls, cpus, cores_used, rc = [], [], [], None
    for _ in range(runs):
        cmd, stdin, args = invocation(binary, case)
        wrapper = [TIME_BIN, '-f', 'ROOFCPU %e %U %S'] if TIME_BIN else []
        t0 = time.perf_counter()
        p = subprocess.run(wrapper + cmd + args, stdin=stdin, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=1800)
        wall = time.perf_counter() - t0
        walls.append(wall)
        rc = p.returncode
        m = CPUTIME.search(p.stderr)
        if m:
            cpu = float(m.group(2)) + float(m.group(3))
            cpus.append(cpu)
            if wall > 0:
                cores_used.append(cpu / wall)
        if case['stdin']:
            stdin.close()
    return dict(wall_s=statistics.median(walls), wall_runs=walls, rc=rc,
                cpu_s=statistics.median(cpus) if cpus else None,
                cores=round(statistics.median(cores_used), 2) if cores_used else None)


NUM = re.compile(r'==\d+== ([A-Za-z0-9 ]+?):\s*([\d,]+)')


def cachegrind(binary, case, out_file, timeout):
    tools = (('ir', IR_ONLY),) if os.environ.get('ROOF_IR_ONLY') else (('sim', CACHEGRIND), ('ir', IR_ONLY))
    timed_out = None
    for label, tool in tools:
        cmd, stdin, args = invocation(binary, case)
        cg = str(out_file) + '.' + label
        try:
            p = subprocess.run(tool + ['--cachegrind-out-file=' + cg] + cmd + args, stdin=stdin,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            # fall through to the cheaper IR-only tool instead of giving up
            timed_out = label
            continue
        finally:
            if case['stdin']:
                stdin.close()
            Path(cg).unlink(missing_ok=True)
        counts = {' '.join(m.group(1).split()): int(m.group(2).replace(',', ''))
                  for m in NUM.finditer(p.stderr.decode('utf8', 'replace'))}
        if p.returncode == 0 and 'I refs' in counts:
            return dict(icount_method='callgrind-' + label, instructions=counts.get('I refs'),
                        d_refs=counts.get('D refs'), d1_misses=counts.get('D1 misses'),
                        ll_misses=counts.get('LL misses'), lld_misses=counts.get('LLd misses'))
    return dict(icount_method='timeout-' + timed_out, instructions=None) if timed_out else \
        dict(icount_method='failed', instructions=None)


def one_task(task, work, runs, timeout, want_cache, langs):
    case = make_case(task, work)
    row = dict(task=task, input_bytes=case['bytes'])
    bins = {}
    for lang in langs:
        out = work / ('%s_%s' % (task, lang.replace('-', '_')))
        ok, p = build(task, lang, out)
        row[lang + '_build_ok'] = ok
        row[lang + '_source'] = SOURCE[lang]
        if not ok:
            row[lang + '_build_error'] = p.stderr.decode('utf8', 'replace')[-400:]
        bins[lang] = out
        if lang.startswith('ail') and ok:
            strict = subprocess.run(build_cmd(task, lang, TASKS_SRC / task / SOURCE[lang],
                                              work / ('%s_%s_strict' % (task, lang.replace('-', '_'))),
                                              strict=True),
                                    capture_output=True, timeout=1800)
            row[lang + '_path'] = 'typed' if strict.returncode == 0 else 'general'
            if strict.returncode != 0:
                lines = strict.stderr.decode('utf8', 'replace').splitlines()
                for i, line in enumerate(lines):
                    if 'why not typed' in line:
                        row[lang + '_why_not_typed'] = ((lines[i - 1] if i else '') + ' | ' + line).strip()[:300]
                        break
    for lang in langs:
        if not row.get(lang + '_build_ok'):
            continue
        t = time_runs(bins[lang], case, runs)
        row[lang + '_wall_s'] = round(t['wall_s'], 4)
        row[lang + '_wall_runs'] = [round(w, 4) for w in t['wall_runs']]
        row[lang + '_rc'] = t['rc']
        row[lang + '_cpu_s'] = round(t['cpu_s'], 4) if t['cpu_s'] is not None else None
        row[lang + '_cores'] = t['cores']
        if want_cache:
            row[lang] = cachegrind(bins[lang], case, work / ('%s_%s.cg' % (task, lang.replace('-', '_'))), timeout)
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
    ap.add_argument('--langs', default=','.join(LANGS))
    ap.add_argument('--cache-timeout', type=int, default=1200)
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--merge', action='store_true',
                    help='update the existing programs.json instead of replacing it (keep other languages)')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in args.tasks.split(',') if t]
    langs = [l for l in args.langs.split(',') if l]
    print('hardware PMU (perf_event_open instructions):', 'yes' if perf_available() else 'no -> valgrind cachegrind',
          flush=True)
    with tempfile.TemporaryDirectory(prefix='roof-') as tmp:
        work = Path(tmp)
        rows = {}
        if args.merge and (out / 'programs.json').is_file():
            try:
                rows = json.loads((out / 'programs.json').read_text())
            except ValueError:
                rows = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(one_task, t, work, args.runs, args.cache_timeout, not args.no_cache, langs): t
                    for t in tasks}
            for fut in concurrent.futures.as_completed(futs):
                t = futs[fut]
                try:
                    fresh = fut.result()
                except Exception as e:
                    fresh = dict(task=t, error='%s: %s' % (type(e).__name__, e))
                rows.setdefault(t, {}).update(fresh)
                (out / 'programs.json').write_text(json.dumps(rows, indent=1) + '\n')
                print('done', t, flush=True)
    (out / 'programs.json').write_text(json.dumps(rows, indent=1) + '\n')
    cols = ['task', 'lang', 'source', 'wall_s', 'instructions', 'llc_misses', 'd1_misses', 'icount_method', 'path']
    print('\t'.join(cols))
    for t in tasks:
        r = rows.get(t, {})
        for lang in langs:
            sub = r.get(lang) or {}
            print('\t'.join(str(x) for x in [t, lang, r.get(lang + '_source'), r.get(lang + '_wall_s'),
                                             sub.get('instructions'), sub.get('lld_misses'), sub.get('d1_misses'),
                                             sub.get('icount_method'), r.get(lang + '_path', '')]))


if __name__ == '__main__':
    main()
