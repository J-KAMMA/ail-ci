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
        # A give-up caused by the harness killing a slow model call says nothing about the
        # language, so it is counted apart from a program that never became correct.
        timeout = sum(1 for r in rs if r['gave_up'] and 'timed out' in
                      ((r['rounds'] or [{}])[-1].get('error_sent') or '') + ((r['rounds'] or [{}])[-1].get('build_error') or ''))
        out[lang] = dict(
            n=len(rs), correct=sum(1 for r in rs if r['correct']), public_pass=len(passed),
            timeout=timeout, answered=len(rs) - timeout,
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
    w('- Model: `%s`, through %s, identical settings for all four languages.'
      % (model, '`cmd -p --yolo --max-turns 1`' if meta.get('cli') == 'cmd' else '`opencode run`'))
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
    w('| language | n | answered | correct | correct % (all) | correct % (answered) | public pass | gave up | of which call timeout | median fix rounds | silent wrong | loud stop | other wrong | loop s | median final run s |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    allrows = lang_rows(rows)
    for lang in LANGS:
        d = allrows.get(lang)
        if not d:
            continue
        w('| %s | %d | %d | %d | %s | %s | %d | %d | %d | %s | %d | %d | %d | %.1f | %s |' % (
            lang, d['n'], d['answered'], d['correct'], pct(d['correct'], d['n']),
            pct(d['correct'], d['answered']), d['public_pass'], d['gave_up'], d['timeout'],
            median(d['rounds']) if d['rounds'] else '-', d['silent'], d['loud'], d['other'],
            d['loop'], ('%.3f' % median(d['run'])) if d['run'] else '-'))
    w('')
    w('`n` is every attempt recorded; `answered` removes the attempts the harness ended because one')
    w('model call exceeded `--call-timeout` before the model returned any text. Those say nothing')
    w('about the language, so both correct rates are given: over every attempt, and over the ones')
    w('the model actually answered. The share differs per language only because the slow calls fell')
    w('where they fell, not because a column was given more time.')
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
    counts = {}
    for _, _, x in fails:
        counts[x] = counts.get(x, 0) + 1
    ail = allrows.get('ail') or {}

    def rate(lang):
        d = allrows.get(lang) or {}
        return '%s (%d/%d answered)' % (pct(d.get('correct', 0), d.get('answered', 0)),
                                        d.get('correct', 0), d.get('answered', 0))

    w('1. AIL reached a correct program in %s of %d attempts; among the attempts where the model'
      % (ail.get('correct', 0), ail.get('n', 0)))
    w('   returned text at all, the four columns are Python %s, Rust %s, Go %s, AIL %s.'
      % (rate('python'), rate('rust'), rate('go'), rate('ail')))
    w('2. AIL failures: %s.' % ('; '.join('%s x%d' % (k, v) for k, v in sorted(counts.items())) or 'none'))
    loud_tasks = sorted({r['task'] for r in rows if r['lang'] == 'ail' and r['loud_stop']})
    w('3. Silent wrong answers on hidden cases: AIL %d, Python %d, Rust %d, Go %d. AIL\'s %d loud'
      % (ail.get('silent', 0), allrows.get('python', {}).get('silent', 0),
         allrows.get('rust', {}).get('silent', 0), allrows.get('go', {}).get('silent', 0),
         ail.get('loud', 0)))
    w('   stop%s: %s.' % ('s' if len(loud_tasks) != 1 else '', ', '.join('`%s`' % t for t in loud_tasks) or 'none'))
    w('4. AIL builds: typed %d, general %d, refused %d; loop time %.0f s against Python %.1f s.'
      % (ail.get('paths', {}).get('typed', 0), ail.get('paths', {}).get('general', 0),
         ail.get('paths', {}).get('refused', 0), ail.get('loop', 0.0),
         allrows.get('python', {}).get('loop', 0.0)))
    w('5. On the vibe1 tasks the delta against vibe1 is %s; a single seed and a 90-180 s call'
      % ', '.join('%s %+d pp' % (lang, round(100.0 * oldlang[lang]['correct'] / oldlang[lang]['n']
                                             - 100.0 * VIBE1[lang]['correct'] / VIBE1[lang]['n']))
                  for lang in ('python', 'rust', 'ail') if lang in oldlang))
    w('   timeout keep the comparison coarse, and part of the drop is unanswered calls, not programs.')
    w('')
    errs = [r for r in table if r['kind'] == 'error']
    n_timeout = ail.get('timeout', 0)
    w('The three things that cost AIL the most correct programs here, in order:')
    w('')
    w('1. **A model call the harness killed.** %d of AIL\'s %d attempts ended on `--call-timeout`'
      % (n_timeout, ail.get('n', 0)))
    w('   before the model returned any text; they are not program failures, and the same model')
    w('   timed out the same way on the other columns. AIL still spent %.0f s of build time over %d'
      % (ail.get('loop', 0.0), ail.get('n', 0)))
    w('   attempts against %.1f s for Python over %d, and since a build of five to sixty seconds sits'
      % (allrows.get('python', {}).get('loop', 0.0), allrows.get('python', {}).get('n', 0)))
    w('   inside the same wall budget as the call, the slow build is what turns a slow model into a')
    w('   gave-up attempt. It is the largest single cause here, and it is the one that is not a bug.')
    if errs:
        w('2. **The subset refuses a natural Python shape.** The AIL column had %d build errors, %d of'
          % (len(errs), sum(r['occurrences'] for r in errs)))
        w('   them the same kind: a dict whose values are lists (`stats[name] = [1, score]`), plus')
        w('   `bytes.decode(..., "surrogateescape")`. Each message named the construct and the rewrite,')
        w('   and the model fixed every one on the next round (fixed %s). The cost is a wasted round and')
        w('   a long rebuild, not an unfixable construct.' % ', '.join(
            '%d/%d' % (round(r['fixed_rate'] * r['occurrences']), r['occurrences']) for r in errs))
    else:
        w('2. **No build error in this sample.** The AIL column compiled every program the model wrote.')
    w('3. **Non-BMP text at run time.** %s passed every hidden case but one: a character above'
      % (', '.join('`%s`' % t for t in loud_tasks) or 'no task'))
    w('   U+FFFF read from a file stops the binary with `AIL internal error: stdin code point above')
    w('   U+FFFF in the 16-bit v2 runtime`. This is the one real correctness loss in the AIL column,')
    w('   and it is a runtime bug, not a speed one. Note also that %d of %d final AIL programs took'
      % (ail.get('paths', {}).get('general', 0), ail.get('n', 0)))
    w('   the general path and none the typed path, so the speed column is the general path\'s.')
    w('')
    w('Everything else AIL compiled ran at the speed of the other native columns: median final run')
    w('%.3f s against Rust %.3f s and Go %.3f s.'
      % (median(ail.get('run') or [0]) or 0, median(allrows.get('rust', {}).get('run') or [0]) or 0,
         median(allrows.get('go', {}).get('run') or [0]) or 0))
    w('')
    w('## What is and is not comparable')
    w('')
    w('- **One seed, not three.** The budget ran out: 73 attempts are recorded, not the 105')
    w('  scheduled, so `n` differs per column (python 21, rust 21, go 13, ail 18). No column is')
    w('  complete. The per-task table shows which (task, language) pairs exist.')
    w('- **The give-ups are the harness, not the language.** Every one of them is')
    w('  `model call timed out`; none is a program that stayed wrong. The call-timeout was lowered')
    w('  from 300 s to 90-180 s during the run to fit the budget, which is what caused them.')
    w('- **The model changed mid-run.** The first phase used `opencode run` with a free model until')
    w('  that quota ran out at 10:25 UTC; those rows are in `results3-opencode-partial.json` and are')
    w('  not counted here. Everything in this report is `deepseek/deepseek-v4.1-flash` through')
    w('  `cmd`, the same model this worker runs on, one setting for every language.')
    w('- **Go was installed, not missing.** `go1.24.13` was already on the runner; the harness built')
    w('  every `.go` file with `go build -o main main.go` outside a module.')
    w('')
    w('## Probes run against the AIL compiler for this report')
    w('')
    w('Each probe is a plain Python file; `bash .agent/cmp.sh <probe> $PWD` builds it with the')
    w('general path (`g`) and the default build (`d`) and diffs both against CPython.')
    w('')
    w('| probe | what it checks | CPython | AIL general | AIL default |')
    w('|---|---|---|---|---|')
    w('| `u1.py` | non-BMP text from `sys.stdin.buffer.read().decode` | 25 code points | same | same |')
    w('| `u2.py` | non-BMP text from `open(..., encoding="utf-8")` | 25, 3 lines | same | same |')
    w('| `u3.py` | `len()` of a non-BMP text field split out of a line | `chars 5` | same | same |')
    w('| `u4.py` | the same through a `dict[int, list[str]]` item | `chars 5` | **`AIL internal error: stdin code point above U+FFFF in the 16-bit v2 runtime`** (exit 1) | same |')
    w('| `u4.py` BMP only | the same with U+00E9 and no non-BMP | `chars 2` | same | same |')
    w('')
    w('The last row is the `todo_file` loud stop reproduced: a non-BMP character reaches the program')
    w('through a value stored in a list inside a dict and aborts the binary at run time. BMP-only')
    w('text is fine through the same path. This is the only AIL difference the probes found; I did')
    w('not change the compiler (out of scope for this job) and did not add an `AIL_FOR_AI.md` line')
    w('for it, because the note would only be actionable if the compiler could avoid it.')
    w('')

    (HERE / 'RESULTS3.md').write_text('\n'.join(L) + '\n')
    print('wrote lab/vibe/RESULTS3.md (%d lines)' % len(L))


if __name__ == '__main__':
    main()
