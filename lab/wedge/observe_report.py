#!/usr/bin/env python3
"""Tables for the obs1 probe from lab/wedge/observe_probe.json (no measurement here).

    python3 lab/wedge/observe_report.py [lab/wedge/observe_probe.json] [--json OUT]

Shares are of the recorder's sampled self time of every function defined in `<kind>.py`.
`bound` is the Amdahl ceiling 1 / (1 - native share) if the native functions took no time at
all; `achieved` is cpython / hybrid (median of 5); `got` is the achieved time saving as a
fraction of the saving the bound allows.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIGS = ('hand', 'hand+obs', 'bare', 'bare+obs')
TRACKED = ('int', 'float', 'bool', 'str', 'list[int]', 'list[float]')


def family(kind):
    if kind is None:
        return '?'
    if isinstance(kind, list):
        return '|'.join(family(k) for k in kind)
    if kind in TRACKED or kind in ('None', 'bytes'):
        return kind
    if kind.startswith('cls:'):
        return 'user class'
    if kind.startswith('list[list') or kind.startswith('list[tuple') or kind.startswith('list[dict'):
        return 'nested list'
    if kind.startswith('list['):
        return kind if kind.count('[') == 1 else 'list[...]'
    return kind.split('[', 1)[0]


def classify(rec, cfg, qual):
    """(bucket, detail) for a function that did not go native in `cfg`."""
    c = rec['configs'][cfg]
    if '.' in qual:
        return 'not-a-top-level-function', ''
    prof = rec['profile'].get(qual)
    if prof is None:
        return 'never-called', ''
    dec = (c.get('decisions') or {}).get(qual)
    why = (c.get('rejected') or {}).get(qual, 'no reason recorded')
    why = why.replace(' stays in CPython', '').split('\n')[0]
    head = why.split(':', 1)[0]
    if dec:
        slots = list(dec['params'].items()) + ([('return', dec['return'])] if dec['return'] else [])
        open_slots = [(n, s) for n, s in slots if not s.get('kept') and not s.get('added')]
        poly = [(n, s) for n, s in open_slots if s['verdict'] == 'poly']
        if poly:
            heads = {k.split('[', 1)[0] for n, s in poly for k in s['kind']}
            detail = '; '.join('%s: %s' % (n, ' | '.join(s['kind'])) for n, s in poly)[:120]
            if len(heads) == 1 and next(iter(heads)) in ('tuple', 'list', 'dict', 'set'):
                # one container type whose element shapes vary (a recursive tuple tree)
                return 'observed-shape-varies: %s' % next(iter(heads)), detail
            return 'observed-polymorphic', detail
        unexp = [(n, s) for n, s in open_slots if s['verdict'] == 'unexpressible']
        if unexp and (head.startswith('unresolved') or 'kind' in head):
            return 'observed-unexpressible: %s' % family(unexp[0][1]['kind']), why[:100]
        if head.startswith('unresolved-return') or why.startswith('result kind'):
            r = dec['return'] or {}
            k = r.get('added') or r.get('kept') or r.get('kind')
            if r.get('verdict') == 'generator':
                return 'generator', ''
            if k and k not in TRACKED:
                return 'return kind not tracked: %s' % family(k), ''
        if head.startswith('unresolved-param') or why.startswith('parameter kind'):
            names = [n.strip() for n in why.split(':', 1)[-1].split(',')]
            for n in names:
                s = dec['params'].get(n) or {}
                k = s.get('added') or s.get('kept') or s.get('kind')
                if k and k not in TRACKED:
                    return 'param kind not tracked: %s' % family(k), ''
    return head, why[:100]


def main(argv):
    src = Path(argv[0]) if argv and not argv[0].startswith('--') else HERE / 'observe_probe.json'
    recs = json.loads(src.read_text())
    out = {}
    # -- native share
    print('## Native share (top-level functions in <kind>.py; time = sampled self time)\n')
    print('| config | native funcs | of | share | native time s | of s | time share |')
    print('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
    total_t = sum(p['self_s'] for r in recs for p in r['profile'].values())
    for cfg in CONFIGS:
        n = sum(len(r['configs'][cfg]['accelerated']) for r in recs)
        f = sum(len(r['functions']) for r in recs)
        t = sum(r['profile'].get(q, {}).get('self_s', 0) for r in recs
                for q in r['configs'][cfg]['accelerated'])
        out.setdefault('share', {})[cfg] = {'native': n, 'functions': f, 'native_s': t,
                                           'total_s': total_t}
        print('| %s | %d | %d | %.1f%% | %.2f | %.2f | %.1f%% |' % (
            cfg, n, f, 100.0 * n / f, t, total_t, 100.0 * t / total_t))
    metrics = (['icount'] if all(r.get('icount') for r in recs) else []) + ['time']
    for metric in metrics:
        per_module(recs, metric, out)
        overhead(recs, metric, out)
    reasons(recs, total_t, out)
    if '--json' in argv:
        Path(argv[argv.index('--json') + 1]).write_text(json.dumps(out, indent=1) + '\n')


def per_module(recs, metric, out):
    label = ('user-space instructions (tools/icount.c), one run' if metric == 'icount'
             else 'wall time, median of 5')
    print('\n## Per module: hybrid / CPython, %s (below 1.0 is faster)\n' % label)
    print('| module | funcs | native hand / h+obs / bare / b+obs | match | CPython | hand | '
          'hand+obs | bare | bare+obs | b+obs share | bound | got |')
    print('| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
    ratios = defaultdict(list)
    for r in recs:
        t = r.get(metric) or {}
        cp = t.get('cpython')
        tot = sum(p['self_s'] for p in r['profile'].values()) or 1e-9
        share = sum(r['profile'].get(q, {}).get('self_s', 0)
                    for q in r['configs']['bare+obs']['accelerated']) / tot
        cells = []
        for cfg in CONFIGS:
            h = t.get(cfg)
            if cp and h:
                ratios[cfg].append(h / cp)
                cells.append('%.3f' % (h / cp))
            else:
                cells.append('n/a')
        bound = 1 / (1 - share) if share < 1 else float('inf')
        h = t.get('bare+obs')
        got = ((cp - h) / (share * cp)) if (cp and h and share > 0.005) else None
        match = all(r['configs'][c]['match'] and r['configs'][c]['source_same_output']
                    for c in CONFIGS) and r['observe_same_output'] and r['cpython']['oracle_match']
        base = ('%.2fG' % (cp / 1e9)) if (metric == 'icount' and cp) else '%.3f s' % (cp or 0)
        print('| `%s` | %d | %s | %s | %s | %s | %.1f%% | %.2fx | %s |' % (
            r['module'], len(r['functions']),
            ' / '.join(str(len(r['configs'][c]['accelerated'])) for c in CONFIGS),
            'yes' if match else 'NO', base, ' | '.join(cells), 100 * share, bound,
            '%.0f%%' % (100 * got) if got is not None else '-'))
    print()
    for cfg in CONFIGS:
        if ratios[cfg]:
            print('- %s: geomean hybrid/CPython %.3fx (range %.3f-%.3f)' % (
                cfg, statistics.geometric_mean(ratios[cfg]), min(ratios[cfg]), max(ratios[cfg])))
    out.setdefault('geomean', {})[metric] = {c: statistics.geometric_mean(v)
                                            for c, v in ratios.items() if v}


def overhead(recs, metric, out):
    print('\n## Recorder overhead (%s / CPython)\n' % metric)
    print('| module | calls | default | --fast | cProfile |')
    print('| --- | ---: | ---: | ---: | ---: |')
    ov = defaultdict(list)
    for r in recs:
        t = r.get(metric) or {}
        cp = t.get('cpython')
        if not cp:
            continue
        calls = sum(p['calls'] for p in r['profile'].values())
        row = []
        for col in ('observe', 'observe_fast', 'cprofile'):
            if t.get(col):
                ov[col].append(t[col] / cp)
                row.append('%.2fx' % (t[col] / cp))
            else:
                row.append('n/a')
        print('| `%s` | %d | %s |' % (r['module'], calls, ' | '.join(row)))
    for col, v in ov.items():
        print('- %s: geomean %.2fx, max %.2fx' % (col, statistics.geometric_mean(v), max(v)))
    out.setdefault('overhead', {})[metric] = {
        c: {'geomean': statistics.geometric_mean(v), 'max': max(v)} for c, v in ov.items()}


def reasons(recs, total_t, out):
    for cfg in ('hand+obs', 'bare+obs'):
        print('\n## Why the rest still refuse, %s (ranked by sampled self time)\n' % cfg)
        print('| # | reason | self s | share | functions | examples |')
        print('| ---: | --- | ---: | ---: | ---: | --- |')
        buckets = defaultdict(lambda: [0.0, 0, []])
        for r in recs:
            native = set(r['configs'][cfg]['accelerated'])
            for qual in r['all_defs']:
                if qual in native:
                    continue
                b, detail = classify(r, cfg, qual)
                s = r['profile'].get(qual, {}).get('self_s', 0)
                e = buckets[b]
                e[0] += s
                e[1] += 1
                e[2].append((s, '%s.%s' % (r['module'], qual), detail))
        rows = sorted(buckets.items(), key=lambda kv: -kv[1][0])
        out.setdefault('reasons', {})[cfg] = [
            {'reason': b, 'self_s': v[0], 'functions': v[1],
             'examples': [x[1] + (' (' + x[2] + ')' if x[2] else '') for x in sorted(v[2], reverse=True)[:4]]}
            for b, v in rows]
        for i, (b, v) in enumerate(rows, 1):
            ex = ', '.join('`%s`' % x[1] for x in sorted(v[2], reverse=True)[:3])
            print('| %d | %s | %.2f | %.1f%% | %d | %s |' % (i, b, v[0], 100 * v[0] / total_t,
                                                            v[1], ex))
    # -- polymorphic detail
    print('\n## Polymorphic slots observed (any config)\n')
    for r in recs:
        for qual, p in r['profile'].items():
            for name, kinds in list(p['params'].items()) + [('return', p['returns'])]:
                ks = set(kinds)
                ks = {k for k in ks if not ('?' in k and any(o.split('[')[0] == k.split('[')[0]
                                                             and '?' not in o for o in ks))}
                if len(ks) > 1:
                    shown = ', '.join(k if len(k) <= 40 else k[:37] + '...' for k in sorted(ks))
                    print('- `%s.%s` %s: %d kinds: %s (self %.2f s)' % (
                        r['module'], qual, name, len(ks), shown[:200], p['self_s']))


if __name__ == '__main__':
    main(sys.argv[1:])
