#!/usr/bin/env python3
"""Collect compare-lab reports into a history and render a static page.

    python3 -I tools/bench_history.py collect
    python3 -I tools/bench_history.py render

`collect` lists the finished compare-lab runs on integ with one `gh run list`, then downloads each
run's compare-report artifact with one `gh run download` per run.  The JSON is read by a `python3 -I`
child process, normalised to one record per run, and appended to lab/compare/history/runs.jsonl;
runs already in the file are skipped.  `render` turns runs.jsonl into lab/compare/history/index.html
with inline SVG charts (no scripts, no external assets).  Both commands are read-only with respect
to GitHub.  The script itself uses only the Python standard library.
"""
import argparse
import html
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HISTORY = REPO / 'lab' / 'compare' / 'history'
RUNS = HISTORY / 'runs.jsonl'
INDEX = HISTORY / 'index.html'
DEFAULT_REPOSITORY = 'J-KAMMA/ail-ci'
DEFAULT_WORKFLOW = 'compare-lab.yml'
DEFAULT_BRANCH = 'integ'
ARTIFACT = 'compare-report'

LANGS = ('ail', 'ail-py', 'c', 'rust', 'go', 'nim', 'python')
AIL_LANGS = ('ail', 'ail-py')
LANG_NAMES = {'ail': 'AIL', 'ail-py': 'AIL (py src)', 'c': 'C', 'rust': 'Rust',
              'go': 'Go', 'nim': 'Nim', 'python': 'Python'}
METRICS = (
    ('wall_ms', 'Wall time', 'ms'),
    ('rss_kib', 'Peak RSS', 'KiB'),
    ('binary_bytes', 'Binary size', 'bytes'),
    ('compile_s', 'Compile time', 's'),
    ('build_disk_kib', 'Build disk', 'KiB'),
    ('instructions', 'Instructions', 'count'),
)
METRIC_KEYS = tuple(key for key, _title, _unit in METRICS)
METRIC_NAMES = {key: title for key, title, _unit in METRICS}

READ_JSON = ('import json, sys\n'
             'with open(sys.argv[1], encoding="utf-8") as handle:\n'
             '    json.dump(json.load(handle), sys.stdout, separators=(",", ":"))\n')


class HistoryError(RuntimeError):
    pass


def _gh(arguments):
    command = ['gh'] + list(arguments)
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise HistoryError('gh is not installed; install the GitHub CLI') from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or '').strip()
        raise HistoryError('%s failed: %s' % (' '.join(command), detail)) from error


def read_json_isolated(path):
    process = subprocess.run([sys.executable, '-I', '-c', READ_JSON, str(path)],
                             check=True, capture_output=True, text=True)
    return json.loads(process.stdout)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def normalise_report(report, run_id, head_sha=None, created_at=None):
    """One record: run, commit, date, tasks -> language -> the six columns (None when absent)."""
    tasks = report.get('tasks') or []
    languages = set()
    for task in tasks:
        languages.update((task.get('results') or {}).keys())
    ordered = [lang for lang in LANGS if lang in languages]
    ordered += sorted(lang for lang in languages if lang not in LANGS)
    normalised = {}
    for task in tasks:
        name = task.get('task')
        if not name:
            continue
        results = task.get('results') or {}
        normalised[str(name)] = {
            lang: {key: _number((results.get(lang) or {}).get(key)) for key in METRIC_KEYS}
            for lang in ordered
        }
    date = report.get('date') or (created_at or '')[:10]
    commit = report.get('head') or (head_sha or '')[:7]
    return {'run': str(run_id), 'commit': str(commit or ''), 'date': str(date or ''),
            'tasks': normalised}


def list_finished_runs(repository, workflow, branch, limit):
    result = _gh(['run', 'list', '-R', repository, '--workflow', workflow, '--branch', branch,
                  '--limit', str(limit), '--json',
                  'databaseId,headSha,createdAt,status,conclusion'])
    runs = json.loads(result.stdout or '[]')
    finished = [run for run in runs if run.get('status') == 'completed']
    return sorted(finished, key=lambda run: (str(run.get('createdAt') or ''), run.get('databaseId') or 0))


def download_report(repository, run_id):
    with tempfile.TemporaryDirectory(prefix='bench-history-') as directory:
        try:
            _gh(['run', 'download', str(run_id), '-R', repository,
                 '-n', ARTIFACT, '-D', directory])
        except HistoryError as error:
            print('skip run %s: %s' % (run_id, error), file=sys.stderr)
            return None
        matches = sorted(Path(directory).rglob('compare-report.json'))
        if not matches:
            print('skip run %s: artifact has no compare-report.json' % run_id, file=sys.stderr)
            return None
        return read_json_isolated(matches[0])


def load_runs(path=RUNS):
    path = Path(path)
    if not path.is_file():
        return []
    runs = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise HistoryError('%s:%d: %s' % (path, number, error)) from error
        if not isinstance(record, dict):
            raise HistoryError('%s:%d: a run must be a JSON object' % (path, number))
        runs.append(record)
    return runs


def run_sort_key(record):
    return (str(record.get('date') or ''), _run_number(record.get('run')))


def _run_number(value):
    text = str(value or '')
    return (0, int(text)) if text.isdigit() else (1, text)


def collect(runs_path=RUNS, repository=DEFAULT_REPOSITORY, workflow=DEFAULT_WORKFLOW,
            branch=DEFAULT_BRANCH, limit=100):
    runs_path = Path(runs_path)
    existing = load_runs(runs_path)
    seen = {str(record.get('run')) for record in existing}
    new = []
    for meta in list_finished_runs(repository, workflow, branch, limit):
        run_id = str(meta.get('databaseId'))
        if run_id in seen:
            print('already recorded: run %s' % run_id)
            continue
        report = download_report(repository, run_id)
        if report is None:
            continue
        record = normalise_report(report, run_id, meta.get('headSha'), meta.get('createdAt'))
        new.append(record)
        seen.add(run_id)
        print('recorded run %s %s %s: %d tasks' %
              (run_id, record['commit'], record['date'], len(record['tasks'])))
    if not new:
        print('no new runs; %d recorded' % len(existing))
        return 0
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    old = runs_path.read_text(encoding='utf-8') if runs_path.is_file() else ''
    if old and not old.endswith('\n'):
        old += '\n'
    added = ''.join(json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n'
                    for record in new)
    handle, temporary = tempfile.mkstemp(prefix='.runs-', dir=str(runs_path.parent))
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(old)
            stream.write(added)
        os.replace(temporary, runs_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('collected %d new run(s); %d in %s' % (len(new), len(existing) + len(new), runs_path))
    return len(new)


def geomean(values):
    values = list(values)
    if not values:
        return None
    return math.exp(sum(math.log(value) for value in values) / len(values))


def _ratio(value, base):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not isinstance(base, (int, float)) or isinstance(base, bool):
        return None
    if value <= 0 or base <= 0:
        return None
    return value / base


def task_signature(record):
    return tuple(sorted((record.get('tasks') or {}).keys()))


def run_ratio(record, lang, metric):
    ratios = []
    for task in sorted(record.get('tasks') or {}):
        languages = record['tasks'][task] or {}
        value = (languages.get(lang) or {}).get(metric)
        base = (languages.get('rust') or {}).get(metric)
        ratio = _ratio(value, base)
        if ratio is not None:
            ratios.append(ratio)
    return geomean(ratios)


def series_segments(xs, ys, signatures):
    segments = []
    current = []
    for index, (x, y) in enumerate(zip(xs, ys)):
        if y is None:
            if current:
                segments.append(current)
                current = []
            continue
        if current and signatures[index] != signatures[index - 1]:
            segments.append(current)
            current = []
        current.append((x, y))
    if current:
        segments.append(current)
    return segments


def _esc(value):
    return html.escape(str(value), quote=True)


def _fmt_ratio(value):
    return '-' if value is None else '%.2fx' % value


def _fmt_value(metric, value):
    if value is None:
        return '-'
    if metric == 'compile_s':
        return '%.2f' % value
    if metric == 'wall_ms':
        return '%.0f' % value
    if metric == 'rss_kib':
        return '%.1f MiB' % (value / 1024)
    if metric == 'build_disk_kib':
        return '%.1f MiB' % (value / 1024)
    if metric == 'binary_bytes':
        return '%.1f KiB' % (value / 1024)
    if metric == 'instructions':
        if value >= 1e9:
            return '%.2fG' % (value / 1e9)
        if value >= 1e6:
            return '%.1fM' % (value / 1e6)
        if value >= 1e3:
            return '%.1fk' % (value / 1e3)
        return '%.0f' % value
    return '%.0f' % value


def svg_chart(runs, metric):
    width, height = 880, 250
    left, right, top, bottom = 78, 24, 34, 58
    plot_width = width - left - right
    plot_height = height - top - bottom
    count = len(runs)
    signatures = [task_signature(record) for record in runs]

    def xpos(index):
        if count <= 1:
            return left + plot_width / 2
        return left + plot_width * index / (count - 1)

    xs = [xpos(index) for index in range(count)]
    series = {lang: [run_ratio(record, lang, metric) for record in runs] for lang in AIL_LANGS}
    values = [value for lang in AIL_LANGS for value in series[lang] if value is not None]
    title = METRIC_NAMES[metric]
    pieces = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s vs Rust over time">' %
              (width, height, _esc(title))]
    pieces.append('<text x="%d" y="20" class="chart-title">%s / Rust (geomean per run, lower is better)</text>' %
                  (left, _esc(title)))
    if not values:
        pieces.append('<text x="%d" y="%d" class="empty">no values to plot</text>' %
                      (left + plot_width / 2, top + plot_height / 2))
        pieces.append('</svg>')
        return '\n'.join(pieces)
    low = min(min(values), 1.0)
    high = max(max(values), 1.0)
    if high == low:
        high = low + (abs(low) or 1.0)
    padding = (high - low) * 0.08
    low -= padding
    high += padding

    def ypos(value):
        return top + (high - value) / (high - low) * plot_height

    for step in range(5):
        value = low + (high - low) * step / 4
        y = ypos(value)
        pieces.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' %
                      (left, y, left + plot_width, y))
        pieces.append('<text x="%d" y="%.1f" class="axis" text-anchor="end">%.2f</text>' %
                      (left - 8, y + 4, value))
    baseline = ypos(1.0)
    pieces.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="baseline"/>' %
                  (left, baseline, left + plot_width, baseline))
    pieces.append('<text x="%d" y="%.1f" class="axis" text-anchor="start">1.00</text>' %
                  (left + plot_width + 4, baseline + 4))
    pieces.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis-line"/>' %
                  (left, top, left, top + plot_height))
    pieces.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis-line"/>' %
                  (left, top + plot_height, left + plot_width, top + plot_height))

    colors = {'ail': '#1f6feb', 'ail-py': '#d1242f'}
    for lang in AIL_LANGS:
        points = series[lang]
        for segment in series_segments(xs, points, signatures):
            coords = ' '.join('%.1f,%.1f' % (x, ypos(value)) for x, value in segment)
            pieces.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' %
                          (coords, colors[lang]))
        for index, value in enumerate(points):
            if value is None:
                continue
            record = runs[index]
            tooltip = '%s: %.3fx, run %s, %s, %s' % (
                LANG_NAMES[lang], value, record.get('run'), record.get('commit'), record.get('date'))
            pieces.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"><title>%s</title></circle>' %
                          (xs[index], ypos(value), colors[lang], _esc(tooltip)))

    label_step = max(1, math.ceil(count / 12))
    for index, record in enumerate(runs):
        if index % label_step and index != count - 1:
            continue
        x = xs[index]
        y = top + plot_height + 18
        pieces.append('<text x="%.1f" y="%d" class="tick" text-anchor="end" transform="rotate(-30 %.1f %d)">%s</text>' %
                      (x, y, x, y, _esc(record.get('commit') or record.get('run'))))
    pieces.append('</svg>')
    return '\n'.join(pieces)


def _summary_line(runs, metric):
    parts = []
    for lang in AIL_LANGS:
        values = [run_ratio(record, lang, metric) for record in runs]
        values = [value for value in values if value is not None]
        if values:
            parts.append('%s geomean %s over %d run(s)' %
                         (LANG_NAMES[lang], _fmt_ratio(geomean(values)), len(values)))
    return '; '.join(parts) if parts else 'no geomean available'


def _latest_table(record, lang):
    tasks = record.get('tasks') or {}
    head = ['task', 'commit'] + ['%s (%s)' % (title, unit) for _key, title, unit in METRICS]
    lines = ['<table>', '<thead><tr>' + ''.join('<th>%s</th>' % _esc(cell) for cell in head) + '</tr></thead>',
             '<tbody>']
    for task in sorted(tasks):
        languages = tasks[task] or {}
        values = languages.get(lang) or {}
        base = languages.get('rust') or {}
        row = [task, str(record.get('commit') or '')]
        for key, _title, _unit in METRICS:
            value = values.get(key)
            reference = base.get(key)
            ratio = _ratio(value, reference)
            text = '%s / %s' % (_fmt_value(key, value), _fmt_value(key, reference))
            if ratio is not None:
                text += ' (%s)' % _fmt_ratio(ratio)
            row.append(text)
        lines.append('<tr>' + ''.join('<td>%s</td>' % _esc(cell) for cell in row) + '</tr>')
    lines += ['</tbody>', '</table>']
    return '\n'.join(lines)


def render_runs(runs):
    runs = sorted(runs, key=run_sort_key)
    parts = ['<!DOCTYPE html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>compare-lab history</title>',
             '<style>',
             'body{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#1f2328;background:#fff}',
             'h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}',
             'p{margin:6px 0}.muted{color:#57606a}.legend span{margin-right:18px}',
             '.swatch{display:inline-block;width:14px;height:3px;vertical-align:middle;margin-right:5px}',
             'svg{max-width:100%;height:auto;margin:8px 0;border:1px solid #d0d7de;border-radius:6px}',
             '.grid{stroke:#eaeef2;stroke-width:1}.baseline{stroke:#8c959f;stroke-width:1;stroke-dasharray:4 3}',
             '.axis-line{stroke:#8c959f;stroke-width:1}.axis{font-size:11px;fill:#57606a}',
             '.tick{font-size:11px;fill:#57606a}.chart-title{font-size:13px;font-weight:600;fill:#1f2328}',
             '.empty{font-size:13px;fill:#57606a;text-anchor:middle}',
             'table{border-collapse:collapse;margin:8px 0 20px;font-size:12px}',
             'th,td{border:1px solid #d0d7de;padding:3px 6px;text-align:right}',
             'th{background:#f6f8fa}td:first-child,th:first-child,td:nth-child(2),th:nth-child(2){text-align:left}',
             '</style>', '</head>', '<body>', '<h1>compare-lab history</h1>']
    if not runs:
        parts.append('<p class="muted">No runs collected yet. Run <code>python3 -I tools/bench_history.py collect</code>.</p>')
        parts += ['</body>', '</html>', '']
        return '\n'.join(parts)
    first, last = runs[0], runs[-1]
    parts.append('<p class="muted">%d run(s), %s (%s) to %s (%s). Each point is the geomean over the tasks '
                 'present in that run; a change of the task list breaks the line.</p>' %
                 (len(runs), _esc(first.get('date')), _esc(first.get('commit')),
                  _esc(last.get('date')), _esc(last.get('commit'))))
    parts.append('<p class="legend"><span><i class="swatch" style="background:#1f6feb"></i>AIL</span>'
                 '<span><i class="swatch" style="background:#d1242f"></i>AIL (py src)</span></p>')
    for key, title, unit in METRICS:
        parts.append('<h2>%s (%s)</h2>' % (_esc(title), _esc(unit)))
        parts.append(svg_chart(runs, key))
        parts.append('<p class="muted">%s</p>' % _esc(_summary_line(runs, key)))
    latest = runs[-1]
    parts.append('<h2>Latest run: %s, %s (%s)</h2>' %
                 (_esc(latest.get('commit')), _esc(latest.get('date')), _esc(latest.get('run'))))
    languages = {lang for task in (latest.get('tasks') or {}).values() for lang in task}
    for lang in AIL_LANGS:
        if lang not in languages:
            continue
        parts.append('<h3>%s vs Rust</h3>' % _esc(LANG_NAMES[lang]))
        parts.append(_latest_table(latest, lang))
    parts.append('<h2>Runs</h2>')
    parts.append('<table><thead><tr><th>run</th><th>date</th><th>commit</th><th>tasks</th></tr></thead><tbody>')
    for record in runs:
        parts.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>' %
                     (_esc(record.get('run')), _esc(record.get('date')),
                      _esc(record.get('commit')), len(record.get('tasks') or {})))
    parts += ['</tbody>', '</table>', '</body>', '</html>', '']
    return '\n'.join(parts)


def render(runs_path=RUNS, out_path=INDEX):
    text = render_runs(load_runs(runs_path))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding='utf-8')
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    collect_parser = sub.add_parser('collect', help='download finished compare-lab reports and append them')
    collect_parser.add_argument('--runs', default=str(RUNS), help='history file (default: %(default)s)')
    collect_parser.add_argument('--repo', default=DEFAULT_REPOSITORY, help='GitHub repository')
    collect_parser.add_argument('--workflow', default=DEFAULT_WORKFLOW, help='workflow file name')
    collect_parser.add_argument('--branch', default=DEFAULT_BRANCH, help='branch')
    collect_parser.add_argument('--limit', type=int, default=100, help='runs to list (default: %(default)s)')
    render_parser = sub.add_parser('render', help='write the static history page')
    render_parser.add_argument('--runs', default=str(RUNS), help='history file (default: %(default)s)')
    render_parser.add_argument('--out', default=str(INDEX), help='HTML output (default: %(default)s)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'collect':
            collect(Path(args.runs), args.repo, args.workflow, args.branch, args.limit)
            return 0
        render(Path(args.runs), Path(args.out))
        print('wrote %s' % args.out)
        return 0
    except HistoryError as error:
        print('error: %s' % error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
