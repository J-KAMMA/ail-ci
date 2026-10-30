#!/usr/bin/env python3
"""Merge the per-task results of compare-lab into a Markdown report and one JSON file.

    python3 lab/compare/merge.py RESULT_DIR --json compare-report.json > compare-report.md

Reads RESULT_DIR/**/result-*.json (one per task, written by run_task.py). One table per metric: rows are
tasks, columns are the languages with the AIL columns first, then the best other language for that row and the
AIL / best ratio (below 1.00 means AIL is better; every metric here is lower-is-better). A program whose stdout
or exit code differs from the CPython reference is shown as `n/a MISMATCH` and takes no part in best or ratio;
a failed build is `build failed`. The two AIL columns are `ail` (the .ail source) and `ail-py` (the CPython
source compiled by AIL); both are compared with the best of c, rust, go, nim and python.
"""
import argparse, json, math, sys
from pathlib import Path

LANGS = ['ail', 'ail-py', 'c', 'rust', 'go', 'nim', 'python']
AIL = ('ail', 'ail-py')
OTHERS = [l for l in LANGS if l not in AIL]
NAMES = {'ail': 'AIL', 'ail-py': 'AIL (py src)', 'c': 'C', 'rust': 'Rust', 'go': 'Go', 'nim': 'Nim', 'python': 'Python'}
BUILD_ONLY = {'compile_s', 'build_disk_kib', 'binary_bytes'}   # CPython has no build step: no value for it


def f_instr(v):
    for div, suffix in ((1e9, 'G'), (1e6, 'M'), (1e3, 'k')):
        if v >= div:
            return '%.2f%s' % (v / div, suffix)
    return '%d' % v


METRICS = [
    ('instructions', 'Instructions (user space)', f_instr),
    ('rss_kib', 'Peak RSS (MiB, /usr/bin/time -v)', lambda v: '%.1f' % (v / 1024)),
    ('binary_bytes', 'Binary size (KiB, as built)', lambda v: '%.0f' % (v / 1024)),
    ('compile_s', 'Compile time (s, median of 3 cold builds)', lambda v: '%.2f' % v),
    ('build_disk_kib', 'Build disk (MiB, fresh build dir with its caches)', lambda v: '%.2f' % (v / 1024)),
    ('wall_ms', 'Wall time (ms, best of the timed runs; shared runner, indicative only)', lambda v: '%.0f' % v),
]


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def usable(r, key):
    """The value of a metric for ranking, or None."""
    if not r or not r.get('build_ok') or r.get('correct') is not True:
        return None
    if key in BUILD_ONLY and r.get('interpreted'):
        return None
    v = r.get(key)
    return v if isinstance(v, (int, float)) and v > 0 else None


def cell(r, key, fmt):
    if r is None:
        return 'not run'
    if not r.get('build_ok'):
        return 'build failed'
    if r.get('status') == 'timeout':
        return 'timeout'
    if key in BUILD_ONLY and r.get('interpreted'):
        return '-'
    v = r.get(key)
    if r.get('correct') is not True:
        return 'n/a MISMATCH'
    return fmt(v) if isinstance(v, (int, float)) else 'n/a'


def table(tasks, key, title, fmt):
    head = ['task'] + [NAMES[l] for l in LANGS] + ['best other', 'AIL / best', 'AIL(py) / best']
    lines = ['### ' + title, '', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    ratios = {l: [] for l in AIL}
    for t in tasks:
        res = t['results']
        best = [(usable(res.get(l), key), l) for l in OTHERS]
        best = min((b for b in best if b[0] is not None), default=None)
        row = [t['task']] + [cell(res.get(l), key, fmt) for l in LANGS]
        row.append('%s (%s)' % (fmt(best[0]), NAMES[best[1]]) if best else '-')
        for l in AIL:
            v = usable(res.get(l), key)
            if v is not None and best:
                ratios[l].append(v / best[0])
                row.append('%.2fx' % (v / best[0]))
            else:
                row.append('-')
        lines.append('| ' + ' | '.join(row) + ' |')
    gm = ['**geomean**'] + [''] * (len(LANGS) + 1)
    for l in AIL:
        g = geomean(ratios[l])
        gm.append('**%.2fx** (n=%d)' % (g, len(ratios[l])) if g else '-')
    lines.append('| ' + ' | '.join(gm) + ' |')
    return lines, {l: dict(geomean=geomean(ratios[l]), n=len(ratios[l])) for l in AIL}


def status_table(tasks):
    head = ['task', 'input'] + [NAMES[l] for l in LANGS] + ['AIL path', 'AIL(py) path']
    lines = ['### Status: output vs the CPython reference, and AIL path', '', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for t in tasks:
        res = t['results']
        row = [t['task'], '%.1f MB' % (t['input_bytes'] / 1e6)]
        for l in LANGS:
            r = res.get(l)
            row.append('not run' if r is None else 'build failed' if not r.get('build_ok') else r.get('status', '-').replace('ok', 'match'))
        for l in AIL:
            r = res.get(l) or {}
            path = r.get('path', '-')
            row.append(path + (' (' + r['why_not_typed'].split('|')[-1].replace('why not typed:', '').strip()[:90] + ')'
                               if path == 'general' and r.get('why_not_typed') else ''))
        lines.append('| ' + ' | '.join(row) + ' |')
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--json', help='write the merged results here')
    args = parser.parse_args()
    tasks = [json.loads(p.read_text()) for p in sorted(Path(args.root).rglob('result-*.json'))]
    if not tasks:
        print('# compare-lab\n\nNo results.')
        return
    first = tasks[0]
    methods = sorted({t.get('icount_method', '?') for t in tasks})
    out = ['# compare-lab: AIL against C, Rust, Go, Nim and Python', '',
           'AIL commit `%s`; %d tasks; instruction counts by `%s`; smoke run: %s.' % (
               first.get('head', '?'), len(tasks), '`, `'.join(methods), 'yes' if first.get('smoke') else 'no'),
           'Every program was run on the same input and its stdout and exit code compared with the CPython `reference.py` of the task. '
           'Ratios are AIL / best other language for that row (below 1.00: AIL is better, all metrics are lower-is-better). '
           'Best-other covers C, Rust, Go, Nim and Python, and only programs whose output matched.', '']
    summary = {}
    out += status_table(tasks) + ['']
    for key, title, fmt in METRICS:
        lines, g = table(tasks, key, title, fmt)
        summary[key] = g
        out += lines + ['']
    out += ['### Toolchain install size (KiB, `du -sk`, once)', '', '| language | KiB |', '|---|---:|']
    out += ['| %s | %s |' % (NAMES.get(k, k), '{:,}'.format(v) if v else 'missing') for k, v in first.get('toolchain_kib', {}).items()]
    out += ['', '### Tools', ''] + ['- %s: %s' % (k, v) for k, v in first.get('tools', {}).items()]
    out += ['', '### Method', '',
            '- Build: gcc -O2 -std=c11; rustc -C opt-level=3; go build; nim c -d:release; AIL `compile` (default build); CPython runs the source.',
            '- Compile time: wall time of the build command, median of 3 cold builds, each in a fresh directory with its own AIL_CACHE, TMPDIR, GOCACHE, GOPATH, nimcache and XDG cache.',
            '- Build disk: `du -sk` of that fresh directory after the first build (binary, caches, leftovers), minus the empty scaffold.',
            '- AIL path: `compile --strict` accepting the program means typed; otherwise the default build used the general path (the reason is quoted).',
            '- Instructions: `perf_event_open` (tools/icount.c) when the runner exposes the counter, otherwise valgrind callgrind Ir. User space only.',
            '- Peak RSS: `/usr/bin/time -v` Maximum resident set size, median of the timed runs.']
    print('\n'.join(out))
    if args.json:
        Path(args.json).write_text(json.dumps(dict(tasks=tasks, geomean_ratio_vs_best_other=summary), indent=1) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
