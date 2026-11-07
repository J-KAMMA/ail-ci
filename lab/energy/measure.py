#!/usr/bin/env python3
"""Energy model for the compare programs: measured RAPL if the runner exposes it, else a published-energy model.

    python3 lab/energy/measure.py --out lab/energy/data --jobs 2

For every `lab/compare/src/<task>` program and every language the task names (AIL building `typed.py`,
AIL building `main.py`, C, Rust, CPython) this writes one row with:

  J measured  package energy from perf power/energy-pkg or /sys/class/powercap, median of three, idle
              baseline subtracted; `null` and method `none` when the runner has no readable counter.
  J model     instructions x E_instr + LLC misses x 64 B x E_dram, with E_instr and E_dram from
              Horowitz, ISSCC 2014 ("Computing's Energy Problem"), 45 nm: 0.1 pJ per 32-bit integer
              add and 640 pJ per 32-bit DRAM read (= 160 pJ/byte). It is an estimate: the instruction
              term is the execute stage only and DRAM is a 45 nm off-chip read, so on a 7 nm EPYC it
              is not a measured package power.
  Landauer    (instructions + 8 x output bytes) x kT ln 2 at 300 K, each retired instruction counted
              as at least one irreversible bit erase plus every output bit; J/floor follows.
  ratios      J model / C's J model and J model / Rust's J model.

Instruction counts and LLC misses are deterministic valgrind cachegrind numbers. AIL and C reuse
`lab/roof/data/programs.json` (the same runner and the same build commands, measured by roof1);
Rust and CPython are measured here. A value cachegrind cannot finish in the timeout is left null,
never guessed. The output byte count for Landauer comes from one run of the C build, because every
language prints the same bytes on the same input (roof1 checked stdout and exit code against C).
"""
import argparse, concurrent.futures, importlib.util, json, math, re, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOF = REPO / 'lab' / 'roof'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
GEN = REPO / 'lab' / 'compare' / 'tasks'
sys.path.insert(0, str(ROOF))
import measure as roof

TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
LANGS = ['ail', 'ail-py', 'c', 'rust', 'python']
SOURCE = {'ail': 'typed.py', 'ail-py': 'main.py', 'c': 'main.c', 'rust': 'main.rs', 'python': 'main.py'}
ROOF_LANG = {'ail': 'ail', 'ail-py': 'ail-py', 'c': 'c'}

# Horowitz, ISSCC 2014, "Computing's Energy Problem (and what we can do about it)", 45 nm:
# 32-bit integer add 0.1 pJ; 32-bit DRAM read 640 pJ (so 160 pJ per byte).
E_INSTR = 0.1e-12
E_DRAM_BYTE = 160e-12
K = 1.380649e-23
T = 300.0
KT_LN2 = K * T * math.log(2.0)
DRAM_LINE = 64

CACHEGRIND = ['valgrind', '--tool=cachegrind', '--cache-sim=yes', '--branch-sim=no',
              '--I1=32768,8,64', '--D1=32768,8,64', '--L2=524288,8,64', '--LL=33554432,16,64']
NUM = re.compile(r'==\d+== ([A-Za-z0-9 ]+?):\s*([\d,]+)')


def make_case(task, work):
    spec = importlib.util.spec_from_file_location('g_' + task, GEN / task / 'gen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _pub, _hid, perf = module.cases(__import__('random').Random('%s-20261012' % task))
    _name, data, args = perf
    path = work / (task + '.bin')
    path.write_bytes(data)
    return dict(stdin=bool(getattr(module, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], bytes=len(data))


def build(task, lang, out):
    src = SRC / task / SOURCE[lang]
    if lang == 'c':
        cmd = ['gcc', '-O2', '-std=c11', '-o', str(out), str(src), '-lm']
    elif lang == 'rust':
        cmd = ['rustc', '-C', 'opt-level=3', '--edition=2021', '-o', str(out), str(src)]
    elif lang == 'python':
        return True, None
    else:
        cmd = roof.build_cmd(task, lang, src, out)
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    return p.returncode == 0 and out.is_file(), p.stderr.decode('utf8', 'replace')[-400:]


def invocation(lang, binary, task, case):
    head = [sys.executable, '-B', str(SRC / task / 'main.py')] if lang == 'python' else [str(binary)]
    return head + case['args']


def run_once(lang, binary, task, case, stdout=None):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run(invocation(lang, binary, task, case), stdin=stdin,
                              stdout=stdout or subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    finally:
        if case['stdin']:
            stdin.close()


def cachegrind(lang, binary, task, case, out_file, timeout):
    """Cachegrind with the runner's real cache geometry; a run that does not finish is null, not guessed."""
    cg = str(out_file) + '.sim'
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        p = subprocess.run(CACHEGRIND + ['--cachegrind-out-file=' + cg] + invocation(lang, binary, task, case),
                           stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(icount_method='timeout-sim', instructions=None, ll_misses=None, lld_misses=None)
    finally:
        if case['stdin']:
            stdin.close()
        Path(cg).unlink(missing_ok=True)
    counts = {' '.join(m.group(1).split()): int(m.group(2).replace(',', ''))
              for m in NUM.finditer(p.stderr.decode('utf8', 'replace'))}
    if p.returncode == 0 and 'I refs' in counts:
        return dict(icount_method='callgrind-sim', instructions=counts.get('I refs'),
                    llc_misses=counts.get('LLd misses'), ll_misses=counts.get('LL misses'),
                    lld_misses=counts.get('LLd misses'))
    return dict(icount_method='failed', instructions=None, ll_misses=None, lld_misses=None)


def model(instructions, llc):
    if instructions is None:
        return None
    return instructions * E_INSTR + (llc or 0) * DRAM_LINE * E_DRAM_BYTE


def landauer(instructions, out_bytes):
    if instructions is None:
        return None
    return (instructions + 8 * (out_bytes or 0)) * KT_LN2


def rapl_method():
    """('perf', None), ('powercap', energy_uj_path) or ('none', None); probe only, never assumes."""
    try:
        p = subprocess.run(['perf', 'stat', '-e', 'power/energy-pkg/', '--', 'true'],
                           capture_output=True, timeout=30)
        if p.returncode == 0 and b'Joules' in p.stderr:
            return 'perf', None
    except Exception:
        pass
    paths = sorted(Path('/sys/class/powercap').glob('*/*/energy_uj')) + sorted(Path('/sys/class/powercap').glob('*/energy_uj'))
    for path in paths:
        try:
            int(path.read_text())
            return 'powercap', str(path)
        except (OSError, ValueError):
            continue
    return 'none', None


def read_uj(path):
    return int(Path(path).read_text())


def measured_energy(method, path, lang, binary, task, case, runs):
    """Package joules, median of `runs`, idle baseline subtracted. Only called when a counter exists."""
    if method == 'powercap':
        idle = []
        for _ in range(3):
            before = read_uj(path)
            time.sleep(2.0)
            idle.append((read_uj(path) - before) / 1e6 / 2.0)
        baseline = sorted(idle)[1]
        values = []
        walls = []
        for _ in range(runs):
            before = read_uj(path)
            t0 = time.perf_counter()
            run_once(lang, binary, task, case)
            wall = time.perf_counter() - t0
            after = read_uj(path)
            values.append((after - before) / 1e6 - baseline * wall)
            walls.append(wall)
        return sorted(values)[len(values) // 2], sorted(walls)[len(walls) // 2]
    # perf power/energy-pkg (read the Joules line; median of runs)
    values, walls = [], []
    for _ in range(runs):
        stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
        t0 = time.perf_counter()
        try:
            p = subprocess.run(['perf', 'stat', '-e', 'power/energy-pkg/', '--'] +
                               invocation(lang, binary, task, case), stdin=stdin,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
        finally:
            if case['stdin']:
                stdin.close()
        wall = time.perf_counter() - t0
        m = re.search(r'([\d.]+)\s+Joules\s+power/energy-pkg', p.stderr.decode('utf8', 'replace'))
        if m:
            values.append(float(m.group(1)))
            walls.append(wall)
    if not values:
        return None, None
    return sorted(values)[len(values) // 2], sorted(walls)[len(walls) // 2]


def roof_row(task, lang):
    path = ROOF / 'data' / 'programs.json'
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text())
    r = rows.get(task, {})
    key = ROOF_LANG.get(lang)
    if key is None:
        return {}
    sub = r.get(key) or {}
    return dict(build_ok=r.get(key + '_build_ok'), path=r.get(key + '_path'),
                wall_s=r.get(key + '_wall_s'), instructions=sub.get('instructions'),
                llc_misses=sub.get('lld_misses'), icount_method=sub.get('icount_method'),
                source=r.get(key + '_source'))


def one_task(task, work, method, powercap, runs, timeout, cache):
    case = make_case(task, work)
    tdir = work / task
    tdir.mkdir(parents=True, exist_ok=True)
    rows = {}
    out_bytes = None
    cbin = tdir / 'c'
    ok, err = build(task, 'c', cbin)
    if ok:
        with open(tdir / 'c.out', 'wb') as fh:
            run_once('c', cbin, task, case, stdout=fh)
        out_bytes = (tdir / 'c.out').stat().st_size
    for lang in LANGS:
        row = dict(task=task, lang=lang, source=SOURCE[lang], out_bytes=out_bytes)
        if lang in ROOF_LANG:
            row.update({k: v for k, v in roof_row(task, lang).items() if v is not None})
            row['source'] = SOURCE[lang]
            if method != 'none':
                # Only read a counter when one exists; the ordinary path reuses roof1's counters.
                if lang == 'c':
                    out, ok = cbin, ok
                else:
                    out = tdir / lang.replace('-', '_')
                    ok, _ = build(task, lang, out)
                if ok:
                    j, wall = measured_energy(method, powercap, lang, out, task, case, runs)
                    row['j_measured'] = j
                    row['wall_s'] = wall if wall is not None else row.get('wall_s')
        else:
            out = tdir / lang
            row['build_ok'], row['build_error'] = build(task, lang, out)
            row['wall_s'] = None
            if row['build_ok']:
                if cache:
                    row.update(cachegrind(lang, out, task, case, tdir / (lang + '.cg'), timeout))
                else:
                    row.update(icount_method='skipped', instructions=None)
                if method != 'none':
                    j, wall = measured_energy(method, powercap, lang, out, task, case, runs)
                    row['j_measured'] = j
                    row['wall_s'] = wall
        if 'j_measured' not in row:
            row['j_measured'] = None
        if not row.get('build_ok'):
            row['instructions'] = None
            row['llc_misses'] = None
            row['icount_method'] = 'refused' if lang.startswith('ail') else 'build-failed'
        row['j_model'] = model(row.get('instructions'), row.get('llc_misses'))
        row['landauer_floor'] = landauer(row.get('instructions'), out_bytes)
        row['j_per_floor'] = (row['j_model'] / row['landauer_floor']
                              if row['j_model'] is not None and row['landauer_floor'] else None)
        rows[lang] = row
    return task, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'data'))
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--cache-timeout', type=int, default=300)
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--merge', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in args.tasks.split(',') if t]
    method, powercap = rapl_method()
    print('RAPL:', method, flush=True)
    result = {}
    if args.merge and (out / 'energy.json').is_file():
        try:
            result = json.loads((out / 'energy.json').read_text())
        except ValueError:
            result = {}
    with tempfile.TemporaryDirectory(prefix='energy-') as tmp:
        work = Path(tmp)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(one_task, t, work, method, powercap, args.runs, args.cache_timeout,
                                not args.no_cache): t for t in tasks}
            for fut in concurrent.futures.as_completed(futs):
                task = futs[fut]
                try:
                    _t, rows = fut.result()
                except Exception as e:
                    rows = {lang: dict(task=task, lang=lang, error='%s: %s' % (type(e).__name__, e))
                            for lang in LANGS}
                result.setdefault(task, {}).update(rows)
                (out / 'energy.json').write_text(json.dumps(result, indent=1) + '\n')
                print('done', task, flush=True)
    result['_meta'] = dict(runner=subprocess.run(['lscpu'], capture_output=True, text=True).stdout
                           .split('Model name:')[-1].splitlines()[0].strip(),
                           rapl=method, e_instr_j=E_INSTR, e_dram_byte_j=E_DRAM_BYTE,
                           kt_ln2_j=KT_LN2, dram_line=DRAM_LINE,
                           source='Horowitz, ISSCC 2014, 45 nm: 32-bit int add 0.1 pJ; 32-bit DRAM read 640 pJ')
    (out / 'energy.json').write_text(json.dumps(result, indent=1) + '\n')
    print('constant kT ln 2 = %.3e J at %.0f K' % (KT_LN2, T))
    print('%-12s %-7s %-8s %12s %12s %8s %12s' % ('task', 'lang', 'status', 'J model', 'J measured', 'x C', 'J/floor'))
    for t in tasks:
        rows = result.get(t, {})
        c = (rows.get('c') or {}).get('j_model')
        for lang in LANGS:
            r = rows.get(lang) or {}
            jm = r.get('j_model')
            print('%-12s %-7s %-8s %12s %12s %8s %12s' % (
                t, lang, 'ok' if r.get('build_ok') else r.get('icount_method', 'n/a'),
                'n/a' if jm is None else '%.3e' % jm, 'n/a' if r.get('j_measured') is None else '%.3e' % r['j_measured'],
                'n/a' if (jm is None or not c) else '%.2f' % (jm / c),
                'n/a' if r.get('j_per_floor') is None else '%.2e' % r['j_per_floor']))


if __name__ == '__main__':
    main()
