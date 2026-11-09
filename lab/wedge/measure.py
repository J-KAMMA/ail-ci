#!/usr/bin/env python3
"""Wall-time and hot-path measurement for lab/wedge (measurement only).

    python3 lab/wedge/measure.py [-j 2] [-o lab/wedge/measure.json] [--only a,b]

Per corpus module:
  cpython      median of 5 `python3 run.py`
  pypy         median of 5 `pypy3 run.py`, with the stdout of every run checked byte-identical
               against the committed `<kind>/expected.txt` (a difference is a PyPy result and is
               recorded in `pypy_match`/`pypy_diff`, never fixed in the sources)
  hybrid       median of 5 `python3 run.py` in the hybrid build directory
  standalone   median of 5 of the AIL binary built from run.py, when it builds
  profile      cProfile of `run.py`, used for the per-function share of CPython's profiled
               self time (cProfile inflates wall time, so these shares rank functions but are
               not shares of real wall time)

The profile is the same program on the same input, so the shares are the hot-path split the
report uses: a function that stays on CPython keeps its own share there.

PyPy is the interpreter in `PYPY` (default: the runner's tool cache; pinned in
`lab/compare_rival/toolchains.env`).  It compiles nothing, so it has no build column.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import pstats
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
CORPUS = HERE / 'corpus'
PYPY = Path(os.environ.get('PYPY', '/opt/hostedtoolcache/PyPy/3.11.17/x64/bin/pypy3'))
RUN_TIMEOUT = 900
BUILD_TIMEOUT = 900
REPS = 5


def _env():
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    return env


def _timeit(cmd, cwd, reps=REPS):
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=RUN_TIMEOUT, env=_env())
        times.append(time.perf_counter() - t0)
        if p.returncode != 0:
            return None, p.returncode, times
    return statistics.median(times), 0, times


def _timeit_pypy(work, expected):
    """PyPy: median of 5, and every run's stdout+exit must equal the committed CPython oracle."""
    exe = PYPY if PYPY.is_file() else shutil.which('pypy3')
    if not exe:
        return {'pypy_error': 'pypy3 not found (set PYPY)'}
    rec = {'pypy_cmd': str(exe)}
    cmd = [str(exe), '-B', 'run.py']
    try:
        ver = subprocess.run([str(exe), '--version'], capture_output=True, text=True, timeout=60)
        rec['pypy_version'] = ' '.join((ver.stdout or ver.stderr).split())
    except Exception as error:
        rec['pypy_version'] = 'missing (%s)' % type(error).__name__
    times, rcs, bad = [], set(), []
    for _ in range(REPS):
        t0 = time.perf_counter()
        try:
            p = subprocess.run(cmd, cwd=str(work), capture_output=True, timeout=RUN_TIMEOUT, env=_env())
        except subprocess.TimeoutExpired:
            rec['pypy_error'] = 'timeout'
            return rec
        times.append(time.perf_counter() - t0)
        rcs.add(p.returncode)
        if p.stdout != expected:
            bad.append(_first_diff(expected, p.stdout))
    rec['pypy_s'] = statistics.median(times) if all(rc == 0 for rc in rcs) else None
    rec['pypy_rc'] = sorted(rcs)[0] if len(rcs) == 1 else sorted(rcs)
    rec['pypy_runs_s'] = [round(t, 6) for t in times]
    rec['pypy_match'] = not bad and rcs == {0}
    rec['pypy_expected_sha256'] = hashlib.sha256(expected).hexdigest()
    if bad:
        rec['pypy_diff'] = bad[0]
        rec['pypy_diff_runs'] = len(bad)
    return rec


def _first_diff(want, got):
    a = want.decode('utf-8', 'replace').splitlines()
    b = got.decode('utf-8', 'replace').splitlines()
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<missing>'
        y = b[i] if i < len(b) else '<missing>'
        if x != y:
            return 'stdout line %d: CPython %r / PyPy %r' % (i + 1, x[:160], y[:160])
    if want != got:
        # splitlines() hides a trailing-newline-only difference; report it as the last line.
        return 'stdout line %d: CPython ends %r / PyPy ends %r' % (
            len(a), want.decode('utf-8', 'replace')[-40:], got.decode('utf-8', 'replace')[-40:])
    return None


def _profile(work, module):
    """cProfile `run.py`; return {function: (tottime, cumtime, ncalls)} for the module."""
    out = work / 'prof.out'
    code = (
        'import cProfile, pstats, runpy, sys\n'
        'cProfile.runctx("runpy.run_path(\\"run.py\\", run_name=\\"__main__\\")",\n'
        '                globals(), {"runpy": runpy}, "%s")\n' % str(out))
    subprocess.run([sys.executable, '-B', '-c', code], cwd=str(work), capture_output=True,
                   timeout=RUN_TIMEOUT, env=_env())
    if not out.is_file():
        return {}
    stats = pstats.Stats(str(out))
    rows = {}
    for (fn, line, name), (cc, nc, tt, ct, _callers) in stats.stats.items():
        if Path(fn).name.startswith(module + '.py'):
            rows[name] = {'tottime': round(tt, 6), 'cumtime': round(ct, 6), 'ncalls': nc}
    return rows


def measure_one(kind_dir):
    kind = kind_dir.name
    rec = {'module': kind}
    work = Path(tempfile.mkdtemp(prefix='wedge-m-%s-' % kind))
    try:
        for f in kind_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, work / f.name)
        c, rc, _ = _timeit([sys.executable, '-B', 'run.py'], work)
        rec['cpython_s'] = c
        rec['cpython_rc'] = rc
        oracle = kind_dir / 'expected.txt'
        rec.update(_timeit_pypy(work, oracle.read_bytes() if oracle.is_file() else b''))
        rec['pypy_oracle'] = oracle.is_file()
        rec['profile'] = _profile(work, kind)
        # hybrid
        hdir = work / 'hybrid'
        p = subprocess.run([sys.executable, '-B', str(AIL), 'build', '--cpython', kind + '.py',
                            '-o', str(hdir)], cwd=str(work), capture_output=True,
                           timeout=BUILD_TIMEOUT, env=_env())
        if p.returncode == 0:
            shutil.copy2(work / 'run.py', hdir / 'run.py')
            try:
                report = json.loads((hdir / 'build.json').read_text())
            except Exception:
                report = {}
            rec['hybrid_native'] = sorted(report.get('accelerated') or [])
            rec['hybrid_rejected'] = report.get('rejected') or {}
            h, rc, _ = _timeit([sys.executable, '-B', 'run.py'], hdir)
            rec['hybrid_s'] = h
            rec['hybrid_rc'] = rc
        else:
            rec['hybrid_error'] = 'build failed'
        # standalone
        p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', 'run.py',
                            '--syntax', 'python', '-o', str(work / 'exe')],
                           cwd=str(work), capture_output=True, timeout=BUILD_TIMEOUT, env=_env())
        if p.returncode == 0:
            s, rc, _ = _timeit([str(work / 'exe')], work)
            rec['standalone_s'] = s
            rec['standalone_rc'] = rc
        else:
            rec['standalone_error'] = (p.stderr.decode('utf-8', 'replace').strip().splitlines()
                                       or ['refused'])[-1][:200]
        return rec
    except Exception as error:
        rec['error'] = '%s: %s' % (type(error).__name__, str(error)[:200])
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('-o', '--out', default=str(HERE / 'measure.json'))
    ap.add_argument('--only')
    args = ap.parse_args()
    dirs = sorted(p for p in CORPUS.iterdir() if (p / 'run.py').is_file())
    if args.only:
        keep = set(args.only.split(','))
        dirs = [d for d in dirs if d.name in keep]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {ex.submit(measure_one, d): d for d in dirs}
        for f in concurrent.futures.as_completed(futs):
            rec = f.result()
            rows.append(rec)
            print('%-16s cpython=%-7s pypy=%-7s pypy_match=%-3s hybrid=%-7s standalone=%-7s native=%d' % (
                rec['module'], rec.get('cpython_s'), rec.get('pypy_s'),
                'yes' if rec.get('pypy_match') else 'NO', rec.get('hybrid_s'),
                rec.get('standalone_s'), len(rec.get('hybrid_native') or [])), flush=True)
    rows.sort(key=lambda r: r['module'])
    Path(args.out).write_text(json.dumps(rows, indent=1) + '\n')
    ok = [r for r in rows if r.get('cpython_s') and r.get('hybrid_s')]
    if ok:
        print('hybrid/cpython time ratio geomean %.3fx on %d modules (below 1.0 is faster)' % (
            statistics.geometric_mean([r['hybrid_s'] / r['cpython_s'] for r in ok]), len(ok)))
    both = [r for r in rows if r.get('pypy_s') and r.get('cpython_s')]
    if both:
        print('pypy/cpython time ratio geomean %.3fx on %d modules; PyPy output matched the oracle on %d of %d' % (
            statistics.geometric_mean([r['pypy_s'] / r['cpython_s'] for r in both]), len(both),
            sum(1 for r in rows if r.get('pypy_match')), len(rows)))
    print('wrote %s' % args.out)


if __name__ == '__main__':
    main()
