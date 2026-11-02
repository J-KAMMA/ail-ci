#!/usr/bin/env python3
"""Publish a compare-lab report as docs/COMPARISON.md.

    python3 tools/compare_publish.py compare-report.json -o docs/COMPARISON.md

The input is the JSON artifact of the compare-lab `report` job (lab/compare/merge.py --json).  The
output keeps every column: instructions, peak RSS, binary size, compile time, build disk and wall
time, for AIL, AIL compiling the CPython source, and the other languages.  Each scorecard cell is a
number and W or L; the method section is merge.METHOD_LINES, unchanged.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'lab' / 'compare'))
import merge  # noqa: E402

KEYS = [metric[0] for metric in merge.METRICS]
SHORT = {'instructions': 'instr', 'rss_kib': 'RSS', 'binary_bytes': 'binary',
         'compile_s': 'compile', 'build_disk_kib': 'disk', 'wall_ms': 'wall'}
RATIOS = [('ail', 'rust'), ('ail', 'best'), ('ail-py', 'rust'), ('ail-py', 'best')]


def load_report(path):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(report.get('tasks'), list):
        raise ValueError('%s: no tasks list' % path)
    return report


def _first(tasks, key):
    for task in tasks:
        if task.get(key) is not None:
            return task[key]
    return None


def _best(task, key):
    found = [(merge.usable(task['results'].get(lang), key), lang) for lang in merge.OTHERS]
    found = [item for item in found if item[0] is not None]
    return min(found, default=(None, None))


def _with(lang, opponent):
    return lang if opponent == 'rust' else 'best'


def _ratio(mine, other):
    return '%.2fx' % (mine / other) if mine is not None and other is not None and other > 0 else '-'


def _flag(mine, other):
    if mine is None or other is None:
        return '-'
    return ('W ' if mine < other else 'L ') + _ratio(mine, other)


def _cases(result):
    if 'cases_public' not in result:
        return 'n/a'
    public, hidden = result['cases_public'], result['cases_hidden']
    passed, total = public[0] + hidden[0], public[1] + hidden[1]
    return '%d/%d%s' % (passed, total, ' FAIL' if result.get('cases_failed') else '')


def _note(result):
    if not result:
        return '-'
    text = result.get('why_not_typed') or result.get('build_error') or result.get('fallback_note') or '-'
    return ' '.join(str(text).split())


def _escape(text):
    return str(text).replace('|', '\\|')


def _path(result):
    if not result:
        return 'not run'
    if not result.get('build_ok'):
        return result.get('path') or 'build failed'
    return result.get('path') or '-'


def scorecard(tasks, lang, opponent):
    """Per task and metric: W/L of the AIL column against one opponent (rust or best other)."""
    label = merge.NAMES['rust'] if opponent == 'rust' else 'the best other language'
    head = ['task', 'path', 'cases'] + [SHORT[key] for key in KEYS]
    lines = ['### %s vs %s' % (merge.NAMES[lang], label), '',
             '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    wins = {key: [0, 0] for key in KEYS}
    for task in tasks:
        result = task['results'].get(lang) or {}
        row = [task['task'], _path(result), _cases(result)]
        for key in KEYS:
            mine = merge.usable(result, key)
            other = (merge.usable(task['results'].get('rust'), key) if opponent == 'rust'
                     else _best(task, key)[0])
            if mine is not None and other is not None:
                wins[key][1] += 1
                if mine < other:
                    wins[key][0] += 1
            row.append(_flag(mine, other))
        lines.append('| ' + ' | '.join(_escape(cell) for cell in row) + ' |')
    lines.append('| **W / n** | | | ' + ' | '.join('**%d/%d**' % tuple(wins[key]) for key in KEYS) + ' |')
    return lines, wins


def summary_counts(report, lang='ail', opponent='rust'):
    tasks = report['tasks']
    counts = {key: [0, 0] for key in KEYS}
    for task in tasks:
        result = task['results'].get(lang) or {}
        for key in KEYS:
            mine = merge.usable(result, key)
            other = (merge.usable(task['results'].get('rust'), key) if opponent == 'rust'
                     else _best(task, key)[0])
            if mine is not None and other is not None:
                counts[key][1] += 1
                if mine < other:
                    counts[key][0] += 1
    return counts


def _range_from(ranges, key, lang):
    item = (ranges or {}).get(key) or {}
    value = item.get(lang)
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
        return float(value[0]), float(value[1])
    return None


def range_counts(report, key, lang='ail', opponent='rust'):
    """W/n that the supplied lower/upper bounds prove, without per-task values.

    All metrics are lower-is-better.  Disjoint ranges prove every task; overlapping ranges prove
    nothing, so the count is 0/0.
    """
    mine = _range_from(report.get('ranges'), key, lang)
    other = _range_from(report.get('ranges'), key, opponent)
    total = len(report['tasks'])
    if not mine or not other or not total:
        return [0, 0]
    if mine[1] < other[0]:
        return [total, total]
    if mine[0] > other[1]:
        return [0, total]
    return [0, 0]


def metric_table(tasks, key, title, fmt, ranges=None):
    head = ['task'] + [merge.NAMES[lang] for lang in merge.LANGS] + ['best other', 'AIL/Rust', 'AIL/best',
                                                                      'AIL(py)/Rust', 'AIL(py)/best']
    lines = ['### ' + title, '', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    ratios = {pair: [] for pair in RATIOS}
    for task in tasks:
        results = task['results']
        best_value, best_lang = _best(task, key)
        row = [task['task']] + [merge.cell(results.get(lang), key, fmt) for lang in merge.LANGS]
        row.append('%s (%s)' % (fmt(best_value), merge.NAMES[best_lang]) if best_value is not None else '-')
        for lang, opponent in RATIOS:
            mine = merge.usable(results.get(lang), key)
            other = merge.usable(results.get('rust'), key) if opponent == 'rust' else best_value
            if mine is not None and other is not None and other > 0:
                ratios[(lang, opponent)].append(mine / other)
                row.append('%.2fx' % (mine / other))
            else:
                row.append('-')
        lines.append('| ' + ' | '.join(_escape(cell) for cell in row) + ' |')
    geo = ['**geomean**'] + [''] * (len(merge.LANGS) + 1)
    for pair in RATIOS:
        value = merge.geomean(ratios[pair])
        geo.append('**%.2fx** (n=%d)' % (value, len(ratios[pair])) if value else '-')
    lines.append('| ' + ' | '.join(geo) + ' |')
    mine = _range_from(ranges, key, 'ail')
    other = _range_from(ranges, key, 'rust')
    has_per_task = any(merge.usable(task['results'].get('ail'), key) is not None for task in tasks)
    if mine and other and not has_per_task:
        if mine[1] < other[0]:
            result = 'AIL lower on %d/%d tasks' % (len(tasks), len(tasks))
        elif mine[0] > other[1]:
            result = 'AIL lower on 0/%d tasks' % len(tasks)
        else:
            result = 'ranges overlap: per-task W/L not known'
        lines += ['', 'Supplied range (no per-task values): AIL %s–%s; Rust %s–%s; %s.' % (
            fmt(mine[0]), fmt(mine[1]), fmt(other[0]), fmt(other[1]), result)]
    return lines


def toolchain_table(tasks):
    first = tasks[0] if tasks else {}
    tools = first.get('tools') or {}
    lines = ['## Toolchain versions', '']
    if tools:
        lines += ['| tool | version |', '|---|---|']
        lines += ['| %s | %s |' % (_escape(key), _escape(value)) for key, value in tools.items()]
    else:
        lines.append('No tool versions in the report.')
    pins = first.get('pins') or {}
    if pins:
        lines += ['', 'Pins: ' + '; '.join('%s=%s' % (key, value) for key, value in pins.items()) + '.']
    sizes = first.get('toolchain_kib') or {}
    if sizes:
        lines += ['', '| toolchain | KiB |', '|---|---:|']
        lines += ['| %s | %s |' % (_escape(merge.NAMES.get(key, key)), '{:,}'.format(value) if value else 'missing')
                  for key, value in sizes.items()]
    return lines


def paths_table(tasks):
    head = ['task', 'AIL path', 'AIL (py src) path', 'AIL cases', 'AIL (py src) cases', 'AIL note', 'AIL (py src) note']
    lines = ['## AIL path and refusals', '', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for task in tasks:
        results = task['results']
        ail = results.get('ail') or {}
        py = results.get('ail-py') or {}
        row = [task['task'], _path(ail), _path(py), _cases(ail), _cases(py), _note(ail), _note(py)]
        lines.append('| ' + ' | '.join(_escape(cell) for cell in row) + ' |')
    return lines


def render(report, source=None, fixture=None, date=None):
    tasks = report['tasks']
    head = report.get('head') or _first(tasks, 'head') or '?'
    when = date or report.get('date') or _first(tasks, 'date') or _first(tasks, 'started') or '?'
    when = str(when).split('T')[0]
    run = report.get('run') or _first(tasks, 'run')
    meta = ['AIL commit `%s`' % head, 'date %s' % when, '%d tasks' % len(tasks)]
    if run:
        meta.append('run %s' % run)
    if fixture:
        meta.append('fixture `%s`' % fixture)
    elif source:
        meta.append('source `%s`' % source)
    lines = ['# AIL language comparison', '', '; '.join(meta) + '.', '']
    lines += toolchain_table(tasks) + ['']
    lines += ['## Scorecards', '']
    for lang in merge.AIL:
        for opponent in ('rust', 'best'):
            lines += scorecard(tasks, lang, opponent)[0] + ['']
    lines += ['## Metrics', '']
    for key, title, fmt in merge.METRICS:
        lines += metric_table(tasks, key, title, fmt, ranges=report.get('ranges')) + ['']
    lines += paths_table(tasks) + ['']
    lines += ['## Method', '', *merge.METHOD_LINES]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('report', help='compare-report.json')
    parser.add_argument('-o', '--output', default='docs/COMPARISON.md')
    parser.add_argument('--date', help='date shown in the header (default: report date)')
    parser.add_argument('--fixture', help='fixture label shown in the header, for example tools/testdata/compare-report.json')
    args = parser.parse_args(argv)
    report = load_report(args.report)
    source = Path(args.report).name
    text = render(report, source=source, fixture=args.fixture, date=args.date)
    Path(args.output).write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
