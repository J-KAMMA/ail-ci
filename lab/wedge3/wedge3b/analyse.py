#!/usr/bin/env python3
"""Rank the hybrid's refusal reasons by the CPython self time they keep.

    python3 analyse.py --profile PROFILE --summary SUMMARY.json --package DIR \
        --modules a.py,b/c.py --out refusals.json

`PROFILE` is an `ail_observe.py run` profile (qualname, file, self_s).  `SUMMARY` is the
hybrid.py output.  Every profiled function defined in one of the listed modules is charged to the
reason the hybrid build reported; a method or nested def the build never looked at is charged to
`not-a-top-level-function`.  `native` self time is the sum for the accelerated names.
"""
import argparse
import collections
import json
import os
import re
from pathlib import Path


def category(reason):
    r = reason.lower()
    if 'not a typed candidate' in r:
        return 'not-a-typed-candidate'
    if 'not a top-level function' in r or 'stays in cpython: only a top-level' in r:
        return 'not-a-top-level-function'
    if 'method of a class' in r:
        return 'method (class with decorators/bases/metaclass)'
    if 'decorated, dunder or non-plain-signature method' in r:
        return 'method (decorated/dunder/non-plain signature)'
    if 'method:' in r:
        return 'method (field kind not expressible)'
    if 'list' in r and ('parameter' in r or 'abi' in r or 'mutation' in r):
        return 'list parameter/ABI'
    if 'return' in r:
        return 'return kind'
    return reason.split(', stays in CPython')[0][:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', required=True)
    ap.add_argument('--summary', required=True)
    ap.add_argument('--package', required=True)
    ap.add_argument('--modules', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    modules = [m.strip() for m in args.modules.split(',') if m.strip()]
    files = {os.path.realpath(os.path.join(args.package, m)): m for m in modules}
    profile = json.loads(Path(args.profile).read_text())
    summary = json.loads(Path(args.summary).read_text())
    rejected = {}
    accelerated = set()
    for rel, rec in summary['modules'].items():
        for k, v in (rec.get('rejected') or {}).items():
            rejected[(rel, k)] = v
        for name in rec.get('accelerated') or []:
            accelerated.add((rel, name))

    buckets = collections.defaultdict(lambda: {'self_s': 0.0, 'functions': 0, 'modules': set(),
                                               'examples': [], 'reasons': collections.Counter()})
    total = 0.0
    native_s = 0.0
    all_functions = 0
    for entry in profile['functions'].values():
        f = os.path.realpath(entry.get('file') or '')
        rel = files.get(f)
        if rel is None:
            continue
        all_functions += 1
        qual = entry['qualname']
        self_s = entry.get('self_s') or 0.0
        total += self_s
        if qual in {n for (m, n) in accelerated if m == rel}:
            native_s += self_s
            continue
        reason = rejected.get((rel, qual))
        if reason is None:
            if '<locals>' in qual:
                cat = 'nested function (not a unit)'
            elif '.' in qual:
                cat = 'method (reason not recorded)'
            else:
                cat = 'not recorded (silent refusal)'
        else:
            cat = category(reason)
        b = buckets[cat]
        b['self_s'] += self_s
        b['functions'] += 1
        b['modules'].add(rel)
        b['reasons'][reason or '(none)'] += 1
        if len(b['examples']) < 6:
            b['examples'].append('%s.%s' % (rel, qual))
    rows = []
    for cat, b in buckets.items():
        rows.append({'category': cat, 'self_s': round(b['self_s'], 4),
                     'share': round(100.0 * b['self_s'] / total, 2) if total else 0.0,
                     'functions': b['functions'], 'modules': sorted(b['modules']),
                     'examples': b['examples'],
                     'reasons': dict(b['reasons'])})
    rows.sort(key=lambda r: -r['self_s'])
    out = {'profile_functions': all_functions, 'total_self_s': round(total, 4),
           'native_self_s': round(native_s, 4), 'native_functions': len(accelerated),
           'rows': rows}
    Path(args.out).write_text(json.dumps(out, indent=1) + '\n')
    print('profiled functions %d  total self %.3f s  native %.3f s (%d functions)' % (
        all_functions, total, native_s, len(accelerated)))
    for r in rows:
        print('%-52s %8.3f s %5.1f%%  %4d  %s' % (
            r['category'][:52], r['self_s'], r['share'], r['functions'],
            ', '.join(r['modules'])[:70]))


if __name__ == '__main__':
    main()
