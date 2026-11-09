#!/usr/bin/env python3
"""Self-check for the benchmark programs: small versions, both builds, against CPython.

Writes /tmp/probes/aicomp_*.ail and runs `bash ~/tools/cmp.sh <probe> <repo>` (falling back to
`.agent/cmp.sh`).  Every probe must report `same stdout` for the `g` and `d` builds.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import bench  # noqa: E402

PROBES = []


def add(name, kind, dt, subs, replacements=()):
    tmpl = bench.KIND[kind][0]
    src = bench.expand(tmpl, dt, subs)
    for old, new in replacements:
        src = src.replace(old, new)
    PROBES.append((name, src))


for dt in ('f64', 'f32'):
    add('matmul_16_%s' % dt, 'matmul', dt, {'@N@': '16'})
    add('elementwise_1000_%s' % dt, 'elementwise', dt, {'@N@': '1000'})
    add('sum_1000_%s' % dt, 'sum', dt, {'@N@': '1000'})
    add('softmax_8_%s' % dt, 'softmax', dt, {'@R@': '8', '@C@': '8'})
    add('mlp_small_%s' % dt, 'mlp', dt, {}, (('b = 64', 'b = 2'), ('i1 = 784', 'i1 = 4'),
                                             ('h = 512', 'h = 3'), ('o = 10', 'o = 2')))
    add('transformer_small_%s' % dt, 'transformer', dt, {}, (('s = 128', 's = 4'), ('d = 64', 'd = 4')))


def main():
    out = Path('/tmp/probes')
    out.mkdir(exist_ok=True)
    cmp = Path.home() / 'tools' / 'cmp.sh'
    if not cmp.is_file():
        cmp = REPO / '.agent' / 'cmp.sh'
    env = dict(os.environ, PYTHONPATH=str(REPO / 'AIL_CURRENT'))
    bad = 0
    for name, src in PROBES:
        path = out / (name + '.ail')
        path.write_text(src.lstrip('\n'))
        r = subprocess.run(['bash', str(cmp), str(path), str(REPO)], env=env,
                           capture_output=True, text=True, timeout=600)
        same = r.stdout.count('same stdout')
        ok = r.returncode == 0 and same == 2
        if not ok:
            bad += 1
        print('%-32s %s' % (name, 'same stdout g+d' if ok else 'FAIL'))
        if not ok:
            print(r.stdout[-3000:])
            print(r.stderr[-1000:])
    print('%d probes, %d failed' % (len(PROBES), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
