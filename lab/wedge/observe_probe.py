#!/usr/bin/env python3
"""obs1 upper-bound probe: observed kinds fed to the existing hybrid selection (measurement only).

    python3 lab/wedge/observe_probe.py [-j 2] [--reps 5] [-o lab/wedge/observe_probe.json] [--only a,b]

Per corpus module this
  1. runs `run.py` once under `AIL_CURRENT/ail_observe.py` and keeps the JSON profile;
  2. builds four hybrids with the unchanged `ail build --cpython`, from four copies of `<kind>.py`:
       hand      the module as committed (hand annotations)               -- wedge baseline
       hand+obs  hand annotations kept, observed monomorphic kinds filled in where none was written
       bare      every annotation stripped                                -- "untyped Python"
       bare+obs  stripped, then only the observed kinds written back
     (`ail_observe.py annotate`, which edits only annotation text);
  3. checks each hybrid's stdout, exit status and last stderr line against the committed
     `expected.txt` (the CPython oracle) and the live CPython run, byte for byte;
  4. times CPython, the recorder (default and `--fast`), cProfile and the four hybrids, `--reps` rounds interleaved
     round-robin so drift hits every column alike, and keeps the median.

Shares use the recorder's own self time of every function defined in `<kind>.py` (methods and
nested functions included, `<module>` excluded).  Phase 2 runs one program at a time.
"""
import argparse
import concurrent.futures
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
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
OBS = ROOT / 'AIL_CURRENT' / 'ail_observe.py'
CORPUS = HERE / 'corpus'
CONFIGS = ('hand', 'hand+obs', 'bare', 'bare+obs')
TIMEOUT = 900

sys.path.insert(0, str(ROOT / 'AIL_CURRENT'))
import ail_observe  # noqa: E402


def _env():
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    return env


def _run(cmd, cwd, timeout=TIMEOUT):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout, env=_env())
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or b'', e.stderr or b''


def _last(data):
    lines = data.decode('utf-8', 'replace').rstrip('\n').splitlines()
    return lines[-1] if lines else ''


def _first_diff(want, got):
    a = want.decode('utf-8', 'replace').splitlines()
    b = got.decode('utf-8', 'replace').splitlines()
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<missing>'
        y = b[i] if i < len(b) else '<missing>'
        if x != y:
            return 'stdout line %d: CPython %r / got %r' % (i + 1, x[:160], y[:160])
    return None


def prepare(kind_dir, base):
    """Phase 1 for one module: profile, four annotated copies, four hybrid builds, correctness."""
    kind = kind_dir.name
    work = base / kind
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rec = {'module': kind, 'configs': {}}
    for f in kind_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, work / f.name)
    rc0, out0, err0 = _run([sys.executable, '-B', 'run.py'], work)
    oracle = (kind_dir / 'expected.txt').read_bytes()
    rec['cpython'] = {'rc': rc0, 'oracle_match': out0 == oracle}
    prof = work / 'profile.json'
    rc1, out1, err1 = _run([sys.executable, '-B', str(OBS), 'run', '-o', str(prof), 'run.py'], work)
    rec['observe_same_output'] = (rc1 == rc0 and out1 == out0)
    profile = json.loads(prof.read_text())
    src_path = work / (kind + '.py')
    rows = ail_observe.functions_for(profile, str(src_path))
    rec['profile'] = {q: {'calls': r['calls'], 'self_s': r['self_s'], 'raised': r['raised'],
                          'params': {p['name']: p['kinds'] for p in r['params']},
                          'big': {p['name']: p['big'] for p in r['params'] if p['big']},
                          'returns': r['returns'], 'generator': r['generator']}
                      for q, r in rows.items() if q != '<module>'}
    text = src_path.read_text(encoding='utf-8')
    variants = {
        'hand': (text, None),
        'hand+obs': ail_observe.annotate_source(text, rows, strip=False),
        'bare': (ail_observe.strip_source(text), None),
        'bare+obs': ail_observe.annotate_source(text, rows, strip=True),
    }
    import ast
    rec['functions'] = sorted(n.name for n in ast.parse(text).body
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    rec['all_defs'] = sorted(ail_observe._def_nodes(ast.parse(text)))
    for cfg, (src, decisions) in variants.items():
        cdir = work / cfg.replace('+', '_')
        cdir.mkdir()
        for f in kind_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, cdir / f.name)
        (cdir / (kind + '.py')).write_text(src, encoding='utf-8')
        c = rec['configs'][cfg] = {'decisions': decisions}
        # the annotated copy itself must still print CPython's bytes
        rcs, outs, errs = _run([sys.executable, '-B', 'run.py'], cdir)
        c['source_same_output'] = (rcs == rc0 and outs == out0)
        hdir = cdir / 'hybrid'
        t0 = time.monotonic()
        rcb, outb, errb = _run([sys.executable, '-B', str(AIL), 'build', '--cpython', kind + '.py',
                                '-o', str(hdir)], cdir)
        c['build_s'] = round(time.monotonic() - t0, 2)
        c['build_rc'] = rcb
        if rcb != 0:
            c['accelerated'], c['rejected'] = [], {}
            c['match'] = False
            c['detail'] = _last(errb)[:300]
            continue
        report = json.loads((hdir / 'build.json').read_text())
        c['accelerated'] = sorted(report.get('accelerated') or [])
        c['rejected'] = report.get('rejected') or {}
        shutil.copy2(cdir / 'run.py', hdir / 'run.py')
        rch, outh, errh = _run([sys.executable, '-B', 'run.py'], hdir)
        same = rch == rc0 and outh == out0 and _last(errh) == _last(err0) and outh == oracle
        c['match'] = same
        c['detail'] = '' if same else (_first_diff(out0, outh) or 'rc %s vs %s / %r vs %r' % (
            rc0, rch, _last(err0)[:120], _last(errh)[:120]))
    return rec


def _columns(recs, base):
    cols = {}
    for rec in recs:
        kind = rec['module']
        work = base / kind
        cols[(kind, 'cpython')] = ([sys.executable, '-B', 'run.py'], work)
        cols[(kind, 'observe')] = ([sys.executable, '-B', str(OBS), 'run', '-o',
                                    str(work / 'p_t.json'), 'run.py'], work)
        cols[(kind, 'observe_fast')] = ([sys.executable, '-B', str(OBS), 'run', '--fast', '-o',
                                         str(work / 'p_f.json'), 'run.py'], work)
        cols[(kind, 'cprofile')] = ([sys.executable, '-B', '-m', 'cProfile', '-o',
                                     str(work / 'cp.out'), 'run.py'], work)
        for cfg in CONFIGS:
            hdir = work / cfg.replace('+', '_') / 'hybrid'
            if rec['configs'][cfg].get('build_rc') == 0 and (hdir / 'run.py').is_file():
                cols[(kind, cfg)] = ([sys.executable, '-B', 'run.py'], hdir)
    return cols


def icount_all(recs, base, icount):
    """User-space instruction counts (tools/icount.c), one run per column: deterministic where
    wall time on a shared WSL laptop is not."""
    cols = _columns(recs, base)
    counts = {}
    for key, (cmd, cwd) in cols.items():
        p = subprocess.run([icount] + cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=TIMEOUT, env=_env())
        try:
            counts[key] = int(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            counts[key] = None
    for rec in recs:
        rec['icount'] = {col: v for (k, col), v in counts.items() if k == rec['module']}
    print('icount done', flush=True)


def time_all(recs, base, reps):
    """Phase 2: one program at a time, interleaved round-robin over columns and modules."""
    cols = _columns(recs, base)
    times = {k: [] for k in cols}
    for r in range(reps):
        for key, (cmd, cwd) in cols.items():
            t0 = time.perf_counter()
            subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=TIMEOUT, env=_env())
            times[key].append(time.perf_counter() - t0)
        print('timing round %d/%d done' % (r + 1, reps), flush=True)
    for rec in recs:
        kind = rec['module']
        rec['time'] = {col: round(statistics.median(v), 4) for (k, col), v in times.items()
                       if k == kind}
        rec['time_raw'] = {col: [round(x, 4) for x in v] for (k, col), v in times.items()
                           if k == kind}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('--reps', type=int, default=5)
    ap.add_argument('-o', '--out', default=str(HERE / 'observe_probe.json'))
    ap.add_argument('--only')
    ap.add_argument('--keep', help='work directory to keep (default: a temporary one)')
    ap.add_argument('--icount', help='tools/icount binary: also record instruction counts')
    ap.add_argument('--reuse', action='store_true',
                    help='load --out and the --keep work directory; redo only the timing')
    args = ap.parse_args()
    dirs = sorted(p for p in CORPUS.iterdir() if (p / 'run.py').is_file())
    if args.only:
        keep = set(args.only.split(','))
        dirs = [d for d in dirs if d.name in keep]
    base = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix='obs1-probe-'))
    base.mkdir(parents=True, exist_ok=True)
    recs = []
    try:
        if args.reuse:
            recs = json.loads(Path(args.out).read_text())
            dirs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futs = [ex.submit(prepare, d, base) for d in dirs]
            for f in concurrent.futures.as_completed(futs):
                rec = f.result()
                recs.append(rec)
                print('%-16s %s' % (rec['module'], '  '.join(
                    '%s=%d%s' % (cfg, len(rec['configs'][cfg]['accelerated']),
                                 '' if rec['configs'][cfg]['match'] else '(MISMATCH)')
                    for cfg in CONFIGS)), flush=True)
        recs.sort(key=lambda r: r['module'])
        if args.icount:
            icount_all(recs, base, args.icount)
        if args.reps > 0:
            time_all(recs, base, args.reps)
        for rec in recs:
            for c in rec['configs'].values():
                c.pop('hybrid_dir', None)
        Path(args.out).write_text(json.dumps(recs, indent=1, sort_keys=True) + '\n')
        print('wrote %s' % args.out)
    finally:
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == '__main__':
    main()
