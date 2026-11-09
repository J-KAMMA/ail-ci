#!/usr/bin/env python3
"""Render lab/vibe/RESULTS3.md from lab/vibe/results3.json.

    python3 lab/vibe/report3.py            # writes lab/vibe/RESULTS3.md

Every number in the report comes from the results file; the prose is a fixed template whose
counts are filled in, so a re-run cannot leave the text out of step with the data.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW_TASKS = sorted(p.name for p in (HERE / 'tasks2').iterdir() if p.is_dir() and (p / 'gen.py').is_file())
VIBE1_TASKS = ['berth_sim', 'chain_relax', 'csv_rollup', 'echo_pack', 'ledger_bin', 'rail_transfer',
               'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
OLD = set(VIBE1_TASKS)
LANGS = ('python', 'rust', 'go', 'ail')

# vibe1 (lab/vibe/RESULTS.md, 2026-11-06) on the old tasks only.
VIBE1 = {'python': dict(n=19, correct=16, gave_up=3),
         'rust': dict(n=12, correct=12, gave_up=0),
         'ail': dict(n=11, correct=7, gave_up=3)}


def pct(a, b):
    return '%.0f%%' % (100.0 * a / b) if b else '-'


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def lang_rows(rows):
    out = {}
    for lang in LANGS:
        rs = [r for r in rows if r['lang'] == lang]
        if not rs:
            continue
        passed = [r for r in rs if r['public_pass']]
        out[lang] = dict(
            n=len(rs), correct=sum(1 for r in rs if r['correct']), public_pass=len(passed),
            gave_up=sum(1 for r in rs if r['gave_up']),
            rounds=[r['rounds_used'] for r in passed],
            silent=sum(r['silent_wrong'] for r in rs), loud=sum(r['loud_stop'] for r in rs),
            other=sum(r['other_wrong'] for r in rs),
            loop=sum(r['loop_seconds'] for r in rs),
            run=[r['final_run_seconds'] for r in rs if r['correct']],
            paths={p: sum(1 for r in rs if r.get('path') == p) for p in ('typed', 'general', 'refused')},
        )
    return out


def classify_failures(rows):
    """Every wrong AIL attempt, classified from its recorded rounds and hidden results."""
    out = []
    for r in rows:
        if r['lang'] != 'ail' or r['correct']:
            continue
        if r['gave_up']:
            last = (r['rounds'] or [{}])[-1]
            err = (last.get('build_error') or '') + (last.get('error_sent') or '')
            if 'timed out' in err:
                kind = 'gave up: model call timed out'
            elif last.get('build_ok') is False:
                kind = 'gave up: build never fixed'
            else:
                kind = 'gave up: public cases never passed'
        else:
            kinds = {h['status'] for h in r['hidden'] if h['status'] != 'pass'}
            if 'silent_wrong' in kinds:
                kind = 'wrong output (silent: same exit, different stdout)'
            elif 'loud_stop' in kinds:
                kind = 'runtime stop (non-zero exit where the reference exits 0)'
            elif 'wrong_exit' in kinds:
                kind = 'wrong output (exit status differs)'
            else:
                kind = 'wrong output'
        out.append((r['task'], r['seed'], kind))
    return out


def main():
    data = json.loads((HERE / 'results3.json').read_text())
    meta = data.get('meta') or {}
    rows = data.get('results') or []
    summary = data.get('summary') or {}
    model = meta.get('model') or '?'
    seeds = meta.get('seeds') or []

    new_rows = [r for r in rows if r['task'] in NEW_TASKS]
    old_rows = [r for r in rows if r['task'] in OLD]
    langs_txt = ', '.join(l for l in LANGS if any(r['lang'] == l for r in rows))

    L = []
    w = L.append
    w('# vibe3 results')
    w('')
    w('The same AI writes the same tasks in Python, Rust, Go and AIL; we count how often it reaches')
    w('a correct program, how many fix rounds that costs, and how often a wrong answer is silent.')
    w('')
    w('- Model: `%s`, through `opencode run`, identical settings for all four languages.' % model)
    w('- Seeds: %s (an independent repeated attempt; the CLI exposes no sampling seed).'
      % ', '.join(str(s) for s in seeds))
    w('- Rounds: up to %d model attempts per (task, language, seed).' % (meta.get('rounds') or 5))
    w('- Languages recorded: %s.' % langs_txt)
    w('- Tasks: %d, of which %d are the vibe1 set (for the delta) and %d are the app-like tasks in'
      % (len({r['task'] for r in rows}), len({r['task'] for r in rows} & OLD), len({r['task'] for r in rows} & set(NEW_TASKS))))
    w('  `lab/vibe/tasks2/` written for vibe3.')
    w('- Columns: python = CPython 3.12 on the `.py` the AI wrote; rust = `rustc -O --edition=2021`;')
    w('  go = `go build -o main main.go` (stdlib only); ail = AIL `compile --syntax python` on the')
    w('  same plain Python the AI wrote for the ail prompt.')
    w('- Oracles: each task\'s own `gen.py` + `reference.py`. Public cases are shown to the AI through')
    w('  the failure feedback; hidden cases never are.')
    w('- Attempts: %s scheduled, %d recorded%s.'
      % (meta.get('scheduled_attempts') or '?', len(rows),
         '; the wall-clock budget stopped scheduling (see the note)' if meta.get('stopped_early') else ''))
    w('')
    w('## Per language, all tasks')
    w('')
    w('| language | n | correct | correct % | public pass | gave up | median fix rounds | silent wrong | loud stop | other wrong | loop s | median final run s |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|')
    allrows = lang_rows(rows)
    for lang in LANGS:
        d = allrows.get(lang)
        if not d:
            continue
        w('| %s | %d | %d | %s | %d | %d | %s | %d | %d | %d | %.1f | %s |' % (
            lang, d['n'], d['correct'], pct(d['correct'], d['n']), d['public_pass'], d['gave_up'],
            median(d['rounds']) if d['rounds'] else '-', d['silent'], d['loud'], d['other'],
            d['loop'], ('%.3f' % median(d['run'])) if d['run'] else '-'))
    w('')
    w('Median fix rounds is over the attempts that passed the public cases; `gave up` is an attempt')
    w('that never did. `silent wrong` counts hidden cases where the program exits like the reference')
    w('but prints something else; `loud stop` counts hidden cases where it exits non-zero where the')
    w('reference exits 0. `loop s` is build plus run time summed over every round of every attempt.')
    w('')
    w('AIL final-program paths: typed %d, general %d, refused %d (n=%d).' % (
        allrows.get('ail', {}).get('paths', {}).get('typed', 0),
        allrows.get('ail', {}).get('paths', {}).get('general', 0),
        allrows.get('ail', {}).get('paths', {}).get('refused', 0),
        allrows.get('ail', {}).get('n', 0)))
    w('')
    w('## Delta against vibe1, on the vibe1 tasks only')
    w('')
    w('vibe1 ran 11 tasks with seeds 0,1 and 42 recorded attempts; this run repeats those tasks.')
    w('')
    w('| language | vibe1 n | vibe1 correct | vibe1 % | vibe3 n | vibe3 correct | vibe3 % | delta |')
    w('|---|---|---|---|---|---|---|---|')
    oldlang = lang_rows(old_rows)
    for lang in ('python', 'rust', 'ail'):
        v1 = VIBE1[lang]
        d = oldlang.get(lang)
        if not d:
            w('| %s | %d | %d | %s | 0 | 0 | - | not run |' % (lang, v1['n'], v1['correct'], pct(v1['correct'], v1['n'])))
            continue
        w('| %s | %d | %d | %s | %d | %d | %s | %+d pp |' % (
            lang, v1['n'], v1['correct'], pct(v1['correct'], v1['n']),
            d['n'], d['correct'], pct(d['correct'], d['n']),
            round(100.0 * d['correct'] / d['n'] - 100.0 * v1['correct'] / v1['n'])))
    w('')
    w('## Per task')
    w('')
    w('`rounds` is one value per seed (x = gave up).')
    w('')
    w('| task | lang | n | correct | rounds | silent | loud | path |')
    w('|---|---|---|---|---|---|---|---|')
    for task in NEW_TASKS + VIBE1_TASKS:
        trs = [r for r in rows if r['task'] == task]
        if not trs:
            continue
        for lang in LANGS:
            rs = [r for r in trs if r['lang'] == lang]
            if not rs:
                continue
            w('| %s | %s | %d | %d | %s | %d | %d | %s |' % (
                task, lang, len(rs), sum(1 for r in rs if r['correct']),
                ','.join('x' if r['gave_up'] else str(r['rounds_used']) for r in rs),
                sum(r['silent_wrong'] for r in rs), sum(r['loud_stop'] for r in rs),
                ','.join(str(r.get('path') or '') for r in rs)))
    w('')

    # AIL compiler messages
    w('## AIL compiler messages')
    w('')
    tables = data.get('ail_errors') or {}
    table = tables.get(model) or []
    w('Every diagnostic the AIL column received, by occurrence, and how often the very next round')
    w('built. `fixed` is the share of occurrences after which the next build succeeded.')
    w('')
    w('| # | kind | message | occurrences | fixed |')
    w('|---|---|---|---|---|')
    for i, r in enumerate(table[:10], 1):
        w('| %d | %s | %s | %d | %s |' % (i, r['kind'], r['message'].replace('|', '\\|')[:200],
                                          r['occurrences'], pct(round(r['fixed_rate'] * r['occurrences']), r['occurrences'])))
    if not table:
        w('| - | - | (no compiler diagnostics recorded) | 0 | - |')
    w('')

    # failure classification
    fails = classify_failures(rows)
    w('## Every AIL failure, classified')
    w('')
    if fails:
        w('| task | seed | class |')
        w('|---|---|---|')
        for task, seed, kind in fails:
            w('| %s | %d | %s |' % (task, seed, kind))
    else:
        w('No AIL attempt failed.')
    w('')

    # verdict
    w('## Verdict')
    w('')
    counts = {k: sum(1 for _, _, x in fails if x == k) for k in sorted({x for _, _, x in fails})}
    ail = allrows.get('ail') or {}
    w('1. AIL reached a correct program in %s of %d attempts (%s); Python %s, Rust %s, Go %s.' % (
        ail.get('correct', 0), ail.get('n', 0), pct(ail.get('correct', 0), ail.get('n', 0)),
        pct(allrows.get('python', {}).get('correct', 0), allrows.get('python', {}).get('n', 0)),
        pct(allrows.get('rust', {}).get('correct', 0), allrows.get('rust', {}).get('n', 0)),
        pct(allrows.get('go', {}).get('correct', 0), allrows.get('go', {}).get('n', 0))))
    w('2. AIL\'s failures: %s.' % ('; '.join('%s: %d' % (k, v) for k, v in counts.items()) or 'none'))
    w('3. Silent wrong answers: AIL %d, Python %d, Rust %d, Go %d (hidden cases).' % (
        ail.get('silent', 0), allrows.get('python', {}).get('silent', 0),
        allrows.get('rust', {}).get('silent', 0), allrows.get('go', {}).get('silent', 0)))
    w('4. AIL builds: typed %d, general %d, refused %d; loop time %.0f s against Python %.1f s.' % (
        ail.get('paths', {}).get('typed', 0), ail.get('paths', {}).get('general', 0),
        ail.get('paths', {}).get('refused', 0), ail.get('loop', 0.0),
        allrows.get('python', {}).get('loop', 0.0)))
    w('5. On the vibe1 tasks the delta against vibe1 is %s.' % ', '.join(
        '%s %+d pp' % (lang, round(100.0 * oldlang[lang]['correct'] / oldlang[lang]['n']
                                   - 100.0 * VIBE1[lang]['correct'] / VIBE1[lang]['n']))
        for lang in ('python', 'rust', 'ail') if lang in oldlang))
    w('')

    (HERE / 'RESULTS3.md').write_text('\n'.join(L) + '\n')
    print('wrote lab/vibe/RESULTS3.md (%d lines)' % len(L))


if __name__ == '__main__':
    main()
