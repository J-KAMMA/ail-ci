#!/usr/bin/env python3
"""Profile lab: where AIL's compile time goes, and how real Python programs fare, measured on a CI runner.

    python3 lab/profile/run.py compile-profile --out OUT [--budget S]
    python3 lab/profile/run.py programs --out OUT --shard I --of N [--budget S]
    python3 lab/profile/run.py report --out OUT IN_DIR...

compile-profile  compiles ~25 representative programs (bench apps, language examples, corpus Python programs) with
                 the build cache off. Per program: median wall time of 3 plain runs; gcc time from a C compiler
                 wrapper ($PIPE_CC) that logs every invocation; the Python side of one extra run under cProfile
                 (a sitecustomize hook profiles the driver and the pyc.py front-end subprocess) is split into
                 phases by module and scaled to the unprofiled non-gcc time. cProfile overhead therefore never
                 touches the gcc share.
programs         the real-program check on lab/corpus/programs (LLM-written stdin->stdout Python programs): compile
                 with `--syntax python` (cache off), run on the 3 inputs, compare stdout/exit code with CPython.
                 Records refused / compile_error / crash / timeout / diff / declared / ok, times and binary size.
report           merges the shard outputs into summary.md and results.jsonl.
"""
import argparse, collections, concurrent.futures as cf, importlib.util, json, os, pstats, re, shutil, statistics
import subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AIL_ROOT = REPO / 'AIL_CURRENT'
AIL = AIL_ROOT / 'ail_chatgpt.py'
CORPUS = REPO / 'lab/corpus'
CAP = 1 << 20

SITECUSTOMIZE = '''
import os, sys
_o = getattr(sys, 'orig_argv', [])
if os.environ.get('AIL_PROF_DIR') and any(a.endswith(('pyc.py', 'ail_chatgpt.py')) for a in _o):
    import atexit, cProfile
    _pr = cProfile.Profile()
    _pr.enable()
    def _dump():
        _pr.disable()
        kind = 'pyc' if any(a.endswith('pyc.py') for a in _o) else 'driver'
        _pr.dump_stats(os.path.join(os.environ['AIL_PROF_DIR'], '%s-%d.prof' % (kind, os.getpid())))
    atexit.register(_dump)
'''

CC_WRAPPER = '''#!/bin/bash
s=$(date +%s%N)
gcc "$@"
rc=$?
e=$(date +%s%N)
echo "$s $e" >> "$AIL_GCC_LOG"
exit $rc
'''

# Heuristic module -> phase map for the Python side (pkg-v12 module names).
FRONT = {'pyfront', 'typedforms', 'typedinherit', 'typedpar', 'rangecheck', 'rebinding', 'shadowing', 'aliasrefuse',
         'compscope', 'strictmode', 'native_diagnostics', 'tryhoist', 'nestfn', 'boolkind', 'callable_types',
         'readonly_bytes_scalar', 'modtables', 'threadlib', 'exctext', 'userexc'}
IRSET = {'semir', 'float64_fusion', 'string_repeat_fusion', 'nested_lists', 'sortkeys', 'iterlower', 'matchlower',
         'filelower', 'hashlower', 'pathlower', 'sqllower', 'urllower', 'tuplegen', 'tupstmt', 'tupexpr', 'tupcalls',
         'tuplam', 'tupcommon', 'raisefrom', 'dunders', 'dunderrt'}
PHASES = ['startup: imports and module bodies', 'driver (ail_chatgpt, syntax, modules)', 'front end (analysis, types)',
          'IR and lowering', 'C generation (emitters, runtime text)', 'stdlib and other Python']


def median(xs):
    return statistics.median(xs) if xs else None


def run(cmd, timeout, env=None, cwd=None, stdin=b''):
    t = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=cwd, input=stdin)
        return r.returncode, r.stdout, r.stderr, False, time.perf_counter() - t
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b'', e.stderr or b'', True, time.perf_counter() - t


def warm_pycache():
    """The compiler runs `python -B` (never writes .pyc): a fresh checkout would pay source compilation of ~140k
    lines on every run. Pre-compile once so the numbers match a normal install."""
    subprocess.run([sys.executable, '-m', 'compileall', '-q', str(AIL_ROOT / 'python/pkg-v12'), str(AIL_ROOT)],
                   capture_output=True)


# ---------------------------------------------------------------- compile profile

def bucket(path, func):
    if path.startswith('<frozen') or func == '<module>' or (path == '~' and any(
            k in func for k in ('marshal', 'builtins.exec', 'builtins.compile', 'create_dynamic', 'exec_module'))):
        return PHASES[0]
    p = path.replace('\\', '/')
    if '/pkg-v12/' in p:
        stem = Path(p).stem
        if stem in FRONT:
            return PHASES[2]
        if stem in IRSET or stem.endswith('lower'):
            return PHASES[3]
        return PHASES[4]
    if p.startswith(str(AIL_ROOT).replace('\\', '/')):
        return PHASES[1]
    return PHASES[5]


WAIT = ('waitpid', 'fork_exec', 'poll', 'select', 'communicate')


def read_profiles(prof_dir):
    """-> (python-side seconds per phase, waiting seconds, {func key: tottime})"""
    phases, wait, funcs = collections.Counter(), 0.0, collections.Counter()
    for f in Path(prof_dir).glob('*.prof'):
        try:
            st = pstats.Stats(str(f))
        except Exception:
            continue
        for (path, line, func), (cc, nc, tt, ct, callers) in st.stats.items():
            if path == '~' and any(w in func for w in WAIT):
                wait += tt
                continue
            phases[bucket(path, func)] += tt
            funcs['%s:%s' % (Path(path).name if path != '~' else 'builtin', func.strip('<>') if path == '~' else func)] += tt
    return phases, wait, funcs


def load_app(name):
    spec = importlib.util.spec_from_file_location('app_' + name, REPO / 'bench/apps' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile_targets(work):
    """[(label, kind, argv after 'compile', prepare callable or None)]"""
    out = []
    for p in sorted((REPO / 'bench/apps').glob('*.py')):
        app = load_app(p.stem)
        d = work / ('app-' + p.stem)
        d.mkdir(exist_ok=True)
        opts = [o.replace('{work}', str(d)) for o in app.AIL_OPTIONS]
        pre = None
        if hasattr(app, 'prepare_ail'):
            def pre(d=d, app=app):
                def cli(*a):
                    r = subprocess.run([sys.executable, '-B', str(AIL), *map(str, a)], cwd=d, capture_output=True, timeout=600)
                    if r.returncode:
                        raise RuntimeError(r.stderr.decode(errors='replace')[-500:])
                app.prepare_ail(d, cli)
        out.append(('bench/' + p.stem, 'bench', [str(AIL_ROOT / app.AIL_SOURCE), *opts], pre))
    mains = sorted((AIL_ROOT / 'language_examples').glob('*_main.ail'))
    for m in mains[::max(1, len(mains) // 10)][:10]:
        out.append(('example/' + m.stem, 'example', [str(m)], None))
    progs = sorted((CORPUS / 'programs').glob('*/t*.py'))
    for m in progs[::max(1, len(progs) // 12)][:12]:
        dst = work / ('py-%s-%s.ail' % (m.parent.name.split('-')[0], m.stem))
        shutil.copyfile(m, dst)
        out.append(('python/%s/%s' % (m.parent.name, m.stem), 'python', [str(dst), '--syntax', 'python'], None))
    return out


def compile_profile(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='profile-'))
    (work / 'site').mkdir()
    (work / 'site/sitecustomize.py').write_text(SITECUSTOMIZE)
    cc = work / 'cc-wrap.sh'
    cc.write_text(CC_WRAPPER)
    cc.chmod(0o755)
    warm_pycache()
    t0 = time.time()
    rows = []
    for label, kind, argv, pre in profile_targets(work):
        if a.budget and time.time() - t0 > a.budget:
            break
        gcc_log = work / 'gcc.log'
        base = dict(os.environ, AIL_NO_CACHE='1', PIPE_CC=str(cc), AIL_GCC_LOG=str(gcc_log), PYTHONHASHSEED='0')
        base.pop('AIL_PROF_DIR', None)
        try:
            if pre:
                pre()
        except Exception as e:
            rows.append(dict(label=label, kind=kind, status='prepare failed: %s' % str(e)[:100]))
            continue
        walls, gccs = [], []
        status = 'ok'
        exe = work / 'exe'
        for i in range(3):
            gcc_log.write_text('')
            exe.unlink(missing_ok=True)
            rc, so, se, to, wall = run([sys.executable, '-B', str(AIL), 'compile', *argv, '-o', str(exe), '--no-cache'], 300, env=base)
            if rc != 0:
                status = 'refused' if rc == 3 else 'compile failed rc=%s' % rc
                break
            g = sum((int(e) - int(s)) / 1e9 for s, e in (l.split() for l in gcc_log.read_text().splitlines() if l.strip()))
            walls.append(wall)
            gccs.append(g)
        if status != 'ok':
            rows.append(dict(label=label, kind=kind, status=status))
            continue
        pdir = work / 'prof'
        shutil.rmtree(pdir, ignore_errors=True)
        pdir.mkdir()
        exe.unlink(missing_ok=True)
        run([sys.executable, '-B', str(AIL), 'compile', *argv, '-o', str(exe), '--no-cache'], 600,
            env=dict(base, AIL_PROF_DIR=str(pdir), PYTHONPATH=str(work / 'site') + os.pathsep + os.environ.get('PYTHONPATH', '')))
        phases, wait, funcs = read_profiles(pdir)
        wall, gcc = median(walls), median(gccs)
        py = max(wall - gcc, 0.0)
        psum = sum(phases.values()) or 1.0
        split = {k: py * v / psum for k, v in phases.items()}
        rows.append(dict(label=label, kind=kind, status='ok', wall_s=wall, gcc_s=gcc, python_s=py,
                         split_s={k: split.get(k, 0.0) for k in PHASES}, top_funcs=funcs.most_common(40),
                         exe_bytes=exe.stat().st_size if exe.exists() else None))
        print('%-50s wall %.2fs gcc %.0f%%' % (label, wall, 100 * gcc / wall), flush=True)
    with open(out / 'compile_profile.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- real programs

def scrub(s):
    return re.sub(r'/(home|Users|mnt/c/Users)/[^/\s]+/', '/home/user/', s)


def classify(cpy, ail):
    c_rc, c_out, c_err = cpy[:3]
    a_rc, a_out, a_err, a_to = ail[:4]
    if a_to:
        return 'timeout'
    if a_rc is not None and (a_rc < 0 or a_rc >= 128):
        return 'crash'
    if a_rc == c_rc and a_out == c_out:
        return 'ok'
    if (a_rc == 1 or (a_rc == 3 and b'limit: int_overflow' in a_err)) and (b'OverflowError' in a_err or b'overflow' in a_err.lower()) \
            and c_out.startswith(a_out):
        return 'declared'
    if a_rc == 1 and b'above U+FFFF' in a_err and c_out.startswith(a_out):
        return 'declared'
    return 'diff'


def norm_reason(msg):
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    r = next((l for l in lines if 'not in the subset' in l or 'refus' in l.lower() or 'unsupported' in l.lower()),
             lines[0] if lines else '')
    r = re.sub(r'^.*?\.ail:\d+(:\d+)?:\s*', '', r)
    r = re.sub(r'^(note|error|AIL ERROR):\s*', '', r)
    r = re.sub(r'^not in the subset:\s*', '', r)
    r = re.sub(r"'[^']*'", "'_'", r)
    r = re.sub(r'`[^`]*`', '`_`', r)
    r = re.sub(r'line \d+', 'line N', r)
    r = re.sub(r'\b\d+\b', 'N', r)
    return scrub(r)[:160]


def compile_program(model, tid, base_dir):
    work = Path(tempfile.mkdtemp(prefix='p-', dir=base_dir))
    src = (CORPUS / 'programs' / model / (tid + '.py')).read_text(encoding='utf-8')
    (work / 'prog.py').write_text(src, encoding='utf-8')
    (work / 'prog.ail').write_text(src, encoding='utf-8')
    category = json.loads((CORPUS / 'tasks' / tid / 'task.json').read_text())['category']
    rec = dict(model=model, task=tid, category=category, lines=src.count('\n') + 1)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONHASHSEED='0', AIL_NO_CACHE='1')
    env.pop('AIL_IR', None)
    exe = work / 'exe'
    rc, so, se, to, wall = run([sys.executable, '-B', str(AIL), 'compile', str(work / 'prog.ail'), '--syntax', 'python',
                                '-o', str(exe), '--no-cache'], 300, env=env)
    rec['compile_ms'] = round(wall * 1000)
    return work, rec, (rc, so, se, to), exe, env


def check_program(work, rec, comp, exe, env, timeout):
    rc, so, se, to = comp
    msg = (se + b'\n' + so).decode('utf-8', 'replace')
    if to:
        return dict(rec, status='timeout', reason='compiler timed out')
    if rc != 0:
        if rc == 3:
            return dict(rec, status='refused', reason=norm_reason(msg), detail=scrub(msg.strip()[-400:]))
        errs = [l for l in msg.splitlines() if 'error' in l.lower()] or msg.splitlines() or ['']
        return dict(rec, status='compile_error', reason='rc=%s: %s' % (rc, scrub(errs[0])[:160]))
    rec['size_bytes'] = exe.stat().st_size
    inputs = [(CORPUS / 'tasks' / rec['task'] / ('in%d.txt' % k)).read_bytes() for k in range(3)]
    classes, detail = [], ''
    cpy_times, ail_times = [], []
    py = [sys.executable, str(work / 'prog.py')]
    for k, inp in enumerate(inputs):
        c1 = run(py, timeout, env=env, stdin=inp)
        c2 = run(py, timeout, env=dict(env, PYTHONHASHSEED='1'), stdin=inp)
        if c1[3] or len(c1[1]) > CAP or (c1[0], c1[1]) != (c2[0], c2[1]):
            classes.append('skipped')
            continue
        ail = run([str(exe)], timeout, env=env, stdin=inp)
        cls = classify(c1, ail)
        classes.append(cls)
        if cls == 'diff' and not detail:
            detail = 'input %d: exit cpython=%s ail=%s' % (k, c1[0], ail[0])
        if k == 2 and cls == 'ok':
            cpy_times = [c1[4], c2[4], run(py, timeout, env=env, stdin=inp)[4]]
            ail_times = [ail[4]] + [run([str(exe)], timeout, env=env, stdin=inp)[4] for _ in range(2)]
    order = ['crash', 'timeout', 'diff', 'declared', 'ok']
    live = [c for c in classes if c != 'skipped']
    status = next((c for c in order if c in live), 'skipped')
    rec = dict(rec, status=status, reason=detail)
    if cpy_times:
        rec['cpython_run_ms'] = round(median(cpy_times) * 1000, 2)
        rec['ail_run_ms'] = round(median(ail_times) * 1000, 2)
        rec['speedup'] = round(median(cpy_times) / max(median(ail_times), 1e-6), 3)
    return rec


def programs(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    warm_pycache()
    items = [(m.name, p.stem) for m in sorted((CORPUS / 'programs').iterdir()) if m.is_dir() for p in sorted(m.glob('t*.py'))]
    items = [x for i, x in enumerate(items) if i % a.of == a.shard]
    base = tempfile.mkdtemp(prefix='progs-')
    t0 = time.time()
    done = 0
    with open(out / 'programs.jsonl', 'w') as jl, cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        # compiles run ahead in a small pool; checks and timings run in this thread
        def comp(item):
            if a.budget and time.time() - t0 > a.budget:
                return None
            return compile_program(item[0], item[1], base)
        futs = [(i, ex.submit(comp, i)) for i in items]
        for item, fut in futs:
            res = fut.result()
            if res is None:
                jl.write(json.dumps(dict(model=item[0], task=item[1], status='not_run')) + '\n')
                continue
            work, rec, c, exe, env = res
            r = check_program(work, rec, c, exe, env, a.timeout)
            jl.write(json.dumps(r) + '\n')
            jl.flush()
            shutil.rmtree(work, ignore_errors=True)
            done += 1
            if done % 10 == 0:
                print('%d/%d programs, %.0fs' % (done, len(items), time.time() - t0), flush=True)


# ---------------------------------------------------------------- report

def table(head, rows):
    return ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows] + ['']


def fmt(x, d=2):
    return '-' if x is None else ('%.*f' % (d, x))


def quart(xs, i):
    return statistics.quantiles(xs, n=4)[i] if len(xs) > 3 else None


def report(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prof, progs = [], []
    for d in a.inputs:
        for f in Path(d).rglob('compile_profile.jsonl'):
            prof += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        for f in Path(d).rglob('programs.jsonl'):
            progs += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    L = ['# AIL profile lab', '', 'Measured on a GitHub Actions runner (CPython %s). Compile times are with the build cache off.' % sys.version.split()[0], '']
    okp = [r for r in prof if r.get('status') == 'ok']
    L += ['## Compile time: where it goes (%d programs profiled, %d skipped)' % (len(okp), len(prof) - len(okp)), '']
    if okp:
        wall = sum(r['wall_s'] for r in okp)
        gcc = sum(r['gcc_s'] for r in okp)
        split = collections.Counter()
        for r in okp:
            for k, v in r['split_s'].items():
                split[k] += v
        rows = [['C compiler (gcc, all invocations)', fmt(gcc, 1), '%.1f%%' % (100 * gcc / wall)]]
        rows += [[k, fmt(split[k], 1), '%.1f%%' % (100 * split[k] / wall)] for k in PHASES]
        rows.append(['**total wall**', fmt(wall, 1), '100%'])
        L += table(['phase', 'seconds (sum)', 'share of wall'], rows)
        L += ['Method: wall = median of 3 runs of `ail_chatgpt.py compile --no-cache`; gcc = measured by a `$PIPE_CC` wrapper; the rest is',
              'split by a cProfile run (tottime by module, waiting on child processes excluded). The module-to-phase map is a heuristic',
              '(`FRONT`/`IRSET` in `run.py`); the function table below is the unambiguous view.', '']
        L += ['### Per program', '']
        L += table(['program', 'wall s', 'gcc s', 'gcc share', 'python s', 'binary KB'],
                   [[r['label'], fmt(r['wall_s']), fmt(r['gcc_s']), '%.0f%%' % (100 * r['gcc_s'] / r['wall_s']),
                     fmt(r['python_s']), fmt((r.get('exe_bytes') or 0) / 1024, 0)] for r in okp])
        shares = sorted(100 * r['gcc_s'] / r['wall_s'] for r in okp)
        L += ['gcc share: median %.0f%%, min %.0f%%, max %.0f%%.' % (median(shares), shares[0], shares[-1]), '']
        funcs = collections.Counter()
        for r in okp:
            for k, v in r['top_funcs']:
                funcs[k] += v
        tot = sum(funcs.values()) or 1
        L += ['### Top Python functions by own time (summed over programs; profiled run)', '']
        L += table(['function', 'seconds', 'share of listed'], [[k.replace('|', '/'), fmt(v, 2), '%.1f%%' % (100 * v / tot)] for k, v in funcs.most_common(15)])
    skipped = [r for r in prof if r.get('status') != 'ok']
    if skipped:
        L += ['Skipped for profiling: ' + ', '.join('%s (%s)' % (r['label'], r['status']) for r in skipped), '']

    L += ['## Real Python programs vs CPython 3.12', '']
    ran = [r for r in progs if r.get('status') != 'not_run']
    if ran:
        STAT = ['ok', 'declared', 'refused', 'compile_error', 'crash', 'timeout', 'diff', 'skipped']
        cnt = collections.Counter(r['status'] for r in ran)
        L += ['%d programs (corpus: LLM-written stdin to stdout tasks), %d not run (time budget).' % (len(ran), len(progs) - len(ran)), '']
        L += table(['status', 'programs', 'share'], [[s, cnt[s], '%.1f%%' % (100 * cnt[s] / len(ran))] for s in STAT])
        L += ['`declared` = AIL stopped at a documented limit (int64 overflow, non-BMP character) with a correct stdout prefix; `skipped` = CPython output was nondeterministic or oversized.', '']
        bycat = collections.defaultdict(collections.Counter)
        for r in ran:
            bycat[r['category']][r['status']] += 1
        L += ['### Pass counts by category', '']
        L += table(['category', 'n'] + STAT + ['pass %'], [[c, sum(v.values())] + [v[s] for s in STAT] +
                   ['%.0f' % (100 * (v['ok'] + v['declared']) / sum(v.values()))] for c, v in sorted(bycat.items())])
        why = collections.Counter(r['reason'] for r in ran if r['status'] == 'refused')
        L += ['### Top 10 refusal reasons', '']
        L += table(['n', 'reason'], [[n, '`%s`' % k.replace('|', '/')] for k, n in why.most_common(10)])
        ce = [r for r in ran if r['status'] in ('compile_error', 'crash', 'diff', 'timeout')]
        if ce:
            L += ['### Failures that are not refusals', '']
            L += table(['model', 'task', 'status', 'detail'], [[r['model'][:12], r['task'], r['status'], (r.get('reason') or '').replace('|', '/')[:120]] for r in ce[:30]])
        sp = [r['speedup'] for r in ran if r.get('speedup')]
        big = [r['speedup'] for r in ran if r.get('speedup') and r['cpython_run_ms'] >= 50]
        L += ['### Run time, compile time, size (status ok programs)', '']
        L += table(['metric', 'value'], [
            ['programs with timings', len(sp)],
            ['median speedup vs CPython (all ok)', fmt(median(sp), 2) + 'x'],
            ['25th / 75th percentile', '%sx / %sx' % (fmt(quart(sp, 0)), fmt(quart(sp, 2)))],
            ['median speedup, CPython run >= 50 ms (%d programs)' % len(big), fmt(median(big), 2) + 'x'],
            ['median CPython run (ms, largest input)', fmt(median([r['cpython_run_ms'] for r in ran if r.get('cpython_run_ms')]), 1)],
            ['median AIL run (ms)', fmt(median([r['ail_run_ms'] for r in ran if r.get('ail_run_ms')]), 1)],
            ['median compile time, compiled programs (s)', fmt((median([r['compile_ms'] for r in ran if r['status'] in ('ok', 'declared', 'diff')]) or 0) / 1000, 2)],
            ['median binary size (KB)', fmt((median([r['size_bytes'] for r in ran if r.get('size_bytes')]) or 0) / 1024, 0)]])
        L += ['Speedups of programs that run for a few milliseconds are dominated by CPython start-up (about 15 ms). Compile times here ran 2 at a time beside the timed runs.', '']
    (out / 'summary.md').write_text('\n'.join(L), encoding='utf-8')
    with open(out / 'results.jsonl', 'w') as f:
        for r in prof:
            f.write(json.dumps(dict(r, set='compile_profile')) + '\n')
        for r in progs:
            f.write(json.dumps(dict(r, set='programs')) + '\n')
    print('\n'.join(L))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('compile-profile')
    c.add_argument('--out', required=True)
    c.add_argument('--budget', type=float, default=1200)
    p = sub.add_parser('programs')
    p.add_argument('--out', required=True)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--of', type=int, default=1)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--timeout', type=float, default=20)
    p.add_argument('--budget', type=float, default=2400)
    r = sub.add_parser('report')
    r.add_argument('--out', required=True)
    r.add_argument('inputs', nargs='+')
    a = ap.parse_args()
    {'compile-profile': compile_profile, 'programs': programs, 'report': report}[a.cmd](a)


if __name__ == '__main__':
    main()
