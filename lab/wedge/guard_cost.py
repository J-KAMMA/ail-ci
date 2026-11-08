#!/usr/bin/env python3
"""obs1: what an entry check costs today, measured on the existing hybrid boundary.

    python3 lab/wedge/guard_cost.py [-o lab/wedge/guard_cost.json]

The hybrid wrapper already checks every argument's type before the native call and falls back to
the original function on a mismatch, so its per-call cost IS the scalar guard cost, and its
list[int] / list[float] conversion (a full copy into a C buffer, checking each element) IS the
"check every element at entry" container guard.  This builds one small module with
`ail build --cpython` and times, per call, CPython against the hybrid:

  add1(n)           scalar guard + boundary, no work
  add1(1 << 70)     the guard fails (int outside int64): fallback cost
  work(n)           a scalar loop of n iterations (the work a guard buys)
  total(xs)         list[int] sum, len 0 / 10 / 1000 / 100000 (per-element entry check + copy)
  ftotal(xs)        list[float] sum, same lengths

Each figure is the median of 5 timings of a fixed loop in one process.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'

MODULE = '''
def add1(n: int) -> int:
    return n + 1


def work(n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s += i * i % 7
        i += 1
    return s


def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s


def ftotal(xs: list[float]) -> float:
    s = 0.0
    for x in xs:
        s += x
    return s
'''

BENCH = r'''
import json, statistics, sys, time
sys.path.insert(0, sys.argv[1])
import gmod
def per_call(fn, arg, n):
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(n):
            fn(arg)
        ts.append((time.perf_counter() - t0) / n)
    return statistics.median(ts) * 1e9
out = {'native': sorted(getattr(gmod, '__ail_native__', []) or [])}
out['add1'] = per_call(gmod.add1, 5, 200000)
out['add1_big'] = per_call(gmod.add1, 1 << 70, 100000)
for n in (10, 100, 1000):
    out['work_%d' % n] = per_call(gmod.work, n, max(200, 200000 // n))
for n in (0, 10, 1000, 100000):
    reps = max(20, 200000 // max(1, n))
    out['total_%d' % n] = per_call(gmod.total, list(range(n)), reps)
    out['ftotal_%d' % n] = per_call(gmod.ftotal, [float(i) for i in range(n)], reps)
print(json.dumps(out))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=str(HERE / 'guard_cost.json'))
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix='obs1-guard-'))
    try:
        (work / 'gmod.py').write_text(MODULE)
        (work / 'bench.py').write_text(BENCH)
        env = dict(os.environ, AIL_NO_CACHE='1')
        env.pop('AIL_UNIFIED_FORCE', None)
        p = subprocess.run([sys.executable, '-B', str(AIL), 'build', '--cpython', 'gmod.py', '-o',
                            str(work / 'h')], cwd=str(work), capture_output=True, text=True, env=env)
        report = json.loads((work / 'h' / 'build.json').read_text())
        res = {'accelerated': report.get('accelerated'), 'rejected': report.get('rejected')}
        for col, d in (('cpython', work), ('hybrid', work / 'h')):
            q = subprocess.run([sys.executable, '-B', str(work / 'bench.py'), str(d)],
                               capture_output=True, text=True, cwd=str(work))
            if q.returncode != 0:
                res[col] = {'error': q.stderr[-400:]}
            else:
                res[col] = json.loads(q.stdout)
        print('accelerated:', res['accelerated'])
        print('%-14s %12s %12s %8s' % ('case', 'CPython ns', 'hybrid ns', 'ratio'))
        for k in res['cpython']:
            if k == 'native':
                continue
            c, h = res['cpython'][k], res['hybrid'].get(k)
            print('%-14s %12.1f %12.1f %8.3f' % (k, c, h, h / c))
        Path(args.out).write_text(json.dumps(res, indent=1) + '\n')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
