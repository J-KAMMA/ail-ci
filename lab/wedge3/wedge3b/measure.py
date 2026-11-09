#!/usr/bin/env python3
"""Median-of-5 wall time for the four builds of each wedge3b workload.

    python3 measure.py --out times.json

Every run is one process under RLIMIT_AS = 2.5 GB, the whole workload at a time.  The hybrid
runs use the pure-Python interpreter with the assembled hybrid package first on PYTHONPATH.
`instructions` uses tools/icount.c (perf_event_open); it is recorded as unavailable where the
kernel denies the counter.
"""
import argparse
import hashlib
import json
import os
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

W3 = Path(__file__).resolve().parent
WORKLOADS = W3 / 'workloads'
ROOT = W3.parents[2]
ICOUNT = Path('/tmp/w3b/icount')
LIMIT = 2500000 * 1024
REPS = 5


def limit():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def run(cmd, env=None, timeout=900):
    e = dict(os.environ)
    e.pop('PYTHONPATH', None)
    if env:
        e.update(env)
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, env=e, preexec_fn=limit)
    return time.perf_counter() - t0, p


def measure(name, cmd, env, cpython_stdout):
    times = []
    out = None
    rc = None
    for _ in range(REPS):
        dt, p = run(cmd, env)
        times.append(dt)
        out, rc = p.stdout, p.returncode
    rec = {'cmd': cmd, 'median_s': round(statistics.median(times), 4),
           'all_s': [round(t, 4) for t in times], 'rc': rc,
           'sha': hashlib.sha256(out or b'').hexdigest()[:16],
           'match': (out == cpython_stdout and rc == 0)}
    if ICOUNT.is_file():
        dt, p = run([str(ICOUNT)] + cmd, env)
        text = p.stdout.decode('utf-8', 'replace').strip()
        rec['instructions'] = int(text) if text.isdigit() else None
        if rec['instructions'] is None:
            rec['instructions_error'] = p.stderr.decode('utf-8', 'replace').strip()[-160:]
    return rec


def library(label, workload, variants):
    path = str(WORKLOADS / workload)
    oracle_python = variants['cpython'][0]
    _, p = run([oracle_python, path])
    cpython_stdout = p.stdout
    rec = {'workload': workload, 'cpython_sha': hashlib.sha256(cpython_stdout).hexdigest()[:16],
           'variants': {}}
    for name, (python, extra_env) in variants.items():
        rec['variants'][name] = measure(name, [python, path], extra_env, cpython_stdout)
        v = rec['variants'][name]
        print('%-10s %-12s %8.4f s  rc=%s match=%s' % (
            label, name, v['median_s'], v['rc'], v['match']), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(W3 / 'times.json'))
    ap.add_argument('--root', default='/tmp/w3b')
    args = ap.parse_args()
    root = args.root
    vpure = root + '/vpure/bin/python'
    vpypy = root + '/vpypy/bin/python'
    vnative = root + '/vnative/bin/python'

    def hyb(lib, variant):
        d = '%s/hyb_%s_%s' % (root, lib, variant)
        return {'PYTHONPATH': d + '/pkg:' + d + '/so'}

    result = {}
    result['pydantic'] = library('pydantic', 'pydantic_records.py', {
        'cpython': (vpure, None),
        'pypy310': (vpypy, None),
        'hybrid_plain': (vpure, hyb('py', 'plain')),
        'hybrid_obs': (vpure, hyb('py', 'obs')),
        'native': (vnative, None),
    })
    result['sqlparse'] = library('sqlparse', 'sql_workload.py', {
        'cpython': (vpure, None),
        'pypy310': (vpypy, None),
        'hybrid_plain': (vpure, hyb('sq', 'plain')),
        'hybrid_obs': (vpure, hyb('sq', 'obs')),
        'native': (vnative, None),
    })
    Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print('wrote', args.out)


if __name__ == '__main__':
    main()
