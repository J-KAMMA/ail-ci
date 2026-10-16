#!/usr/bin/env python3
"""Merge per-config results into one Markdown report.

    python3 lab/flags/merge.py RESULT_DIR > report.md

Reads RESULT_DIR/**/*.json (one per config). Ratios are against gcc-O2 (below 1.00 is better). A config
with any MISMATCH or ERROR row is reported as failed and gets no ratios. Geomean covers programs with a
valid measurement in both the config and the baseline."""
import json, math, sys
from pathlib import Path

ORDER = ['gcc-O2', 'gcc-O3', 'gcc-Os', 'gcc-O2-v3', 'gcc-O2-lto', 'gcc-O2-pgo', 'clang-O2', 'clang-O3', 'zig-O2']
METRICS = [('ir', 'Instructions (callgrind Ir)'), ('rss_kib', 'Peak RSS (KiB)'), ('size', 'Stripped binary size (bytes)')]


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def main(root):
    data = {}
    for p in sorted(Path(root).rglob('*.json')):
        d = json.loads(p.read_text())
        data[d['config']] = d['results']
    configs = [c for c in ORDER if c in data] + sorted(c for c in data if c not in ORDER)
    base = data.get('gcc-O2', {})
    programs = list(base) or sorted({n for r in data.values() for n in r})
    failed = {c: [n for n, r in data[c].items() if r.get('status') != 'ok'] for c in configs}
    out = ['# AIL C backend flags study', '',
           'Same generated C per program, built with each compiler/flags config. Ratios are vs gcc -O2 '
           '(below 1.00 is better). A config whose output differs from the gcc -O2 build on any program is '
           'marked FAILED and gets no ratios.', '']
    out += ['## Geomean vs gcc -O2', '', '| config | ' + ' | '.join(m[1] for m in METRICS) + ' | status |',
            '|---|' + '---|' * (len(METRICS) + 1)]
    for c in configs:
        cells = []
        for key, _ in METRICS:
            rs = []
            for n in programs:
                b, v = base.get(n, {}), data[c].get(n, {})
                if b.get('status') == 'ok' and v.get('status') == 'ok' and b.get(key) and v.get(key):
                    rs.append(v[key] / b[key])
            g = geomean(rs)
            cells.append('FAILED' if failed[c] else ('n/a' if g is None else '%.3f (n=%d)' % (g, len(rs))))
        out.append('| %s | %s | %s |' % (c, ' | '.join(cells), 'FAILED: ' + ', '.join(failed[c]) if failed[c] else 'ok'))
    for key, title in METRICS:
        out += ['', '## ' + title + ' (ratio vs gcc-O2; absolute for gcc-O2)', '',
                '| program | ' + ' | '.join(configs) + ' |', '|---|' + '---|' * len(configs)]
        for n in programs:
            b = base.get(n, {}).get(key)
            cells = []
            for c in configs:
                r = data[c].get(n, {})
                if r.get('status') != 'ok' or not r.get(key):
                    cells.append(r.get('status', 'missing'))
                elif c == 'gcc-O2':
                    cells.append('%d' % r[key])
                else:
                    cells.append('%.3f' % (r[key] / b) if b else 'n/a')
            out.append('| %s | %s |' % (n, ' | '.join(cells)))
    out += ['', '## Notes', '',
            '- Instructions are callgrind totals (deterministic); no wall time is reported because shared runners are noisy.',
            '- gcc-O2-pgo trains on the same example input it is measured on, so it is an upper bound for PGO gain.',
            '- Every config keeps the flags AIL adds itself (-fno-tree-slp-vectorize, -fno-asynchronous-unwind-tables); only the compiler and -O level change.']
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
