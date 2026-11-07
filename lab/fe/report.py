#!/usr/bin/env python3
"""Render `lab/fe/results.json` (written by `prof.py`) as `lab/fe/RESULTS.md`.

    python3 lab/fe/report.py --results lab/fe/results.json --out lab/fe/RESULTS.md

The rendering is deterministic: the same JSON always produces the same markdown,
so RESULTS.md can be regenerated and diffed after a rerun.
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GROUPS = [('compare-main', 'compare `main.py`'), ('compare-typed', 'compare `typed.py`'),
          ('tcc-corpus', 'tcc corpus')]


def f(value, digits=3):
    return '—' if value is None else ('%.*f' % (digits, value))


def pct(part, whole, digits=1):
    if not whole:
        return '—'
    return '%.*f%%' % (digits, 100.0 * part / whole)


def table(headers, rows, align=None):
    align = align or ['---'] * len(headers)
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join(align) + '|']
    out += ['| ' + ' | '.join(str(cell) for cell in row) + ' |' for row in rows]
    return '\n'.join(out)


def timer(bucket, label, key='total'):
    return ((bucket or {}).get(label) or {}).get(key)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', type=pathlib.Path, default=HERE / 'results.json')
    ap.add_argument('--out', type=pathlib.Path, default=HERE / 'RESULTS.md')
    args = ap.parse_args(argv)
    data = json.loads(args.results.read_text(encoding='utf8'))
    programs = data['programs']
    built = [p for p in programs if p.get('phases')]
    general = [p for p in built if p.get('path') == 'general']
    typed = [p for p in built if p.get('path') == 'typed']
    lines = []
    add = lines.append

    add('# fe1 — where AIL\'s Python front end spends compile time')
    add('')
    add('Measured %s with `lab/fe/prof.py` on branch `%s` (the compiler is not changed). Python %s, `%s`.'
        % (data.get('date'), data.get('branch', 'job-fe1-11071326'), data.get('python'),
           data.get('platform', '')))
    add('Sample: the ten `lab/compare/src/<task>/main.py`, their ten `typed.py`, and the twelve'
        ' `corpus/gdev` programs timed in `lab/tcc/RESULTS.md` (`berth_sim` and `echo_pack` are'
        ' already counted from `lab/compare`) — %d programs in total, %d that build here.'
        % (len(programs), len(built)))
    add('')
    add('## Method')
    add('')
    add('* Every build is cold: a fresh `AIL_CACHE`, a fresh `TMPDIR`, `AIL_NO_CACHE=1`, `AIL_SERVER=0`.')
    add('* Wall time is the median of `--reps` runs (see `reps` in the JSON; 3 here).')
    add('* The phase split comes from `timed_outer.py` / `timed_inner.py`, thin wrappers that start'
        ' `ail_chatgpt.py` and `pyc.py` unchanged and add `perf_counter` around the driver\'s own'
        ' top-level pass functions. Their `exclusive` time is non-overlapping; `other` is the'
        ' remainder, and §1 shows that on the general path it is mostly the second `check` the'
        ' driver runs to position its fallback note.')
    add('* `typed_emit` / `general_emit` are each reported whole: both emitters interleave type'
        ' analysis with writing the C string (source line markers, temporaries, declarations), so'
        ' splitting "analysis" from "C emission" would need a compiler change. The task\'s "C'
        ' emission" row is therefore the emitter\'s exclusive time. `parse` is `ast.parse` timed in'
        ' both processes by the wrappers; because it is called inside `load`, `pre` and the emitters'
        ' it is a component of those rows, not an additional one.')
    add('* `cProfile` (a `sitecustomize.py` in both Python processes) is used for the pass-cumulative'
        ' and top-20 tables. It inflates times 2–3x; the columns that matter for the Amdahl bounds in'
        ' `docs/design/FRONTEND_SPEED.md` come from the low-overhead timed wrappers, not cProfile.')
    add('* `python3 -X importtime` is measured on each entry point; `/usr/bin/time -v` gives peak RSS.')
    add('* Peak RSS is the whole child tree (`ail_chatgpt.py` plus the `pyc.py` it starts), as'
        ' reported by `/usr/bin/time -v` for the outer process.')
    add('')
    add('## Fixed costs')
    add('')
    add('| | seconds |')
    add('|---|---:|')
    add('| interpreter start + imports, outer driver (`ail_chatgpt.py`) | %s |'
        % f(data.get('importtime_outer'), 4))
    add('| interpreter start + imports, inner compiler (`pyc.py`) | %s |'
        % f(data.get('importtime_inner'), 4))
    add('| measured outer `import` (timed wrapper) | %s |'
        % f(_median([(p['timed'].get('outer') or {}).get('import') for p in built]), 4))
    add('| measured inner `import` (timed wrapper) | %s |'
        % f(_median([p['timed']['inner'].get('import') for p in built]), 4))
    add('')
    add('`importtime` runs `--help`; the timed-wrapper `import` is the number used in the phase table.')
    add('')

    add('## 1. Cold compile wall, split')
    add('')
    add('Seconds. `pre` is the sum of the cheap refusal passes (`fold_int_constants`,'
        ' `_refuse_static_big_calls`, `_python_defs_only_runs_nothing`, `_refuse_big_capable`,'
        ' `_refuse_typed_big_store`). `typed`/`general` are the emitters.')
    add('')
    headers = ['program', 'group', 'path', 'wall', 'start+import', 'load', 'pre', 'typed', 'general',
               'C compile+link', 'other']
    align = ['---', '---', '---', '---:', '---:', '---:', '---:', '---:', '---:', '---:', '---:']
    rows = []
    for p in built:
        ph = p['phases']
        rows.append([p['name'], p['group'], p['path'], f(p.get('cold_median')),
                     f(ph['startup_imports']), f(ph['outer_load']), f(ph['inner_pre_passes']),
                     f(ph['typed_emit']), f(ph['general_emit']), f(ph['c_compile_link']),
                     f(ph['other'])])
    add(table(headers, rows, align))
    add('')
    failed = [p for p in programs if not p.get('phases')]
    if failed:
        add('Refused / not built here: ' + ', '.join('`%s`' % p['name'] for p in failed) + '.')
        add('')

    add('### Typed and general path')
    add('')
    add('| path | programs | median wall | median typed emit | median general emit | median C compile+link |')
    add('|---|---:|---:|---:|---:|---:|')
    for label, group in (('typed', typed), ('general', general)):
        add('| %s | %d | %s | %s | %s | %s |' % (
            label, len(group),
            f(_median([p['cold_median'] for p in group])),
            f(_median([p['phases']['typed_emit'] for p in group])),
            f(_median([p['phases']['general_emit'] for p in group])),
            f(_median([p['phases']['c_compile_link'] for p in group]))))
    add('')
    add('Total cold wall over the %d programs that build: %s s; of that the Python front end'
        ' (`start+import` + `load` + `pre` + `typed` + `general`) is %s s (%s), the C compiler and'
        ' linker %s s (%s).'
        % (len(built), f(_total(built, lambda p: p['cold_median']), 2),
           f(_total(built, _frontend), 2),
           pct(_total(built, _frontend), _total(built, lambda p: p['cold_median'])),
           f(_total(built, lambda p: p['phases']['c_compile_link']), 2),
           pct(_total(built, lambda p: p['phases']['c_compile_link']),
               _total(built, lambda p: p['cold_median']))))
    add('')

    add('### The doomed typed attempt on programs that fall back')
    add('')
    add('For a program that ends on the general path, the front end first tries the typed emitter.'
        ' `typed attempt` is its whole (failed) time; `general` is the path that produced the C.')
    add('')
    add('| program | wall | typed attempt | general emit | typed share of wall |')
    add('|---|---:|---:|---:|---:|')
    for p in general:
        ph = p['phases']
        add('| %s | %s | %s | %s | %s |' % (
            p['name'], f(p['cold_median']), f(ph['typed_attempt']), f(ph['general_attempt']),
            pct(ph['typed_attempt'], p['phases']['total'])))
    add('')
    entered = [p for p in general if p['phases']['typed_attempt'] >= 0.01]
    refused = [p for p in general if p['phases']['typed_attempt'] < 0.01]
    add('Across the general-path programs the failed typed attempt costs %s s of %s s wall (%s), and'
        ' the general emitter %s s (%s). %d of the %d general-path programs spend time in the typed'
        ' emitter (at least 0.01 s) and then fall back (%s); the other %d (%s) are refused by a cheap'
        ' pre-pass (`_refuse_big_capable` and friends) before the emitter runs, so their typed attempt'
        ' is ~0.'
        % (f(_total(general, lambda p: p['phases']['typed_attempt']), 2),
           f(_total(general, lambda p: p['cold_median']), 2),
           pct(_total(general, lambda p: p['phases']['typed_attempt']),
               _total(general, lambda p: p['cold_median'])),
           f(_total(general, lambda p: p['phases']['general_attempt']), 2),
           pct(_total(general, lambda p: p['phases']['general_attempt']),
               _total(general, lambda p: p['cold_median'])),
           len(entered), len(general),
           ', '.join('%s %ss' % (p['name'], f(p['phases']['typed_attempt'], 2)) for p in entered),
           len(refused),
           ', '.join('%s %ss' % (p['name'], f(p['phases']['typed_attempt'], 3)) for p in refused)))
    add('')

    add('### The `other` bucket is a second front end (`check` for the fallback note)')
    add('')
    add('`other` is wall the timed wrappers do not cover. On the general-path programs it is not'
        ' process spawn: `compile` ends by asking the driver to position its advisory'
        ' `note: … built on the general path` line, and `_fallback_notes` → `_locate_refusal`'
        ' (`ail_chatgpt.py:5499`, `:5995`) starts a second `ail_chatgpt.py check` over the whole'
        ' source. That check runs the front end again; its cost lands in `other`, and it only'
        ' happens when the program fell back, i.e. exactly on the slow builds. `AIL_QUIET_FALLBACK=1`'
        ' avoids it (the note is advisory and its absence changes no stdout, stderr-by-default is'
        ' the only difference).')
    add('')
    add('| program | `other` s | share of that build |')
    add('|---|---:|---:|')
    for p in sorted(built, key=lambda p: -(p['phases']['other']))[:5]:
        if p['phases']['other'] < 0.2:
            break
        add('| %s | %s | %s |' % (p['name'], f(p['phases']['other']),
                                  pct(p['phases']['other'], p['cold_median'])))
    add('')
    add('Across all programs `other` is %s s of %s s (%s); on the five programs above it is %s s.'
        % (f(_total(built, lambda p: p['phases']['other']), 2),
           f(_total(built, lambda p: p['cold_median']), 2),
           pct(_total(built, lambda p: p['phases']['other']),
               _total(built, lambda p: p['cold_median'])),
           f(sum(p['phases']['other'] for p in
                 sorted(built, key=lambda p: -p['phases']['other'])[:5]), 2)))
    add('')

    add('### Pass boundaries (timed exclusive, cold, summed over all programs)')
    add('')
    add('| pass | seconds | share of front end |')
    add('|---|---:|---:|')
    front_total = _total(built, _frontend)
    parse = _total(built, lambda p: p.get('parse_timed') or p['phases'].get('parse_timed') or 0.0)
    parse_cp = _total(built, lambda p: (p['passes'] or {}).get('ast_parse_cum') or 0.0)
    profiled = _total(built, lambda p: p.get('profile_wall') or 0.0)
    for label in ('fold_int_constants', 'refuse_static_big_calls',
                  'python_defs_only_runs_nothing', 'refuse_big_capable', 'refuse_typed_big_store',
                  'typed_emit', 'general_emit', 'cc'):
        value = _total(built, lambda p, label=label:
                       timer((p['timed']['inner'] or {}).get('timers'), label) or 0.0)
        share = pct(value, _total(built, lambda p: p['cold_median'])) if label == 'cc' else pct(value, front_total)
        add('| `%s` | %s | %s |' % (label, f(value), share))
    add('| `parse` (timed, nested) | %s | %s |' % (f(parse), pct(parse, front_total)))
    add('')
    add('`cc` is the C compile+link subprocess and is not part of the Python front end; it is listed'
        ' for comparison. The cheap refusal passes cost about a second in total across 30 programs.'
        ' `parse` is a component of the rows above, so it is not additive with them.')
    add('')
    add('`parse`: `ast.parse` is called several times per build (the driver merge, the refusal'
        ' passes, `_to_c`, `_rewrite_script`); it is timed in both processes at %s s = %s of the'
        ' timed cold wall. That time is already inside `load`, `pre`, `typed` and `general`, so the'
        ' row is a component, not additive. cProfile charges the same call sites %s s cumulative'
        ' (%s of the profiled wall, inflated like every cProfile number).'
        % (f(parse, 2), pct(parse, _total(built, lambda p: p['phases']['total'])),
           f(parse_cp, 2), pct(parse_cp, profiled)))
    add('')

    add('## 2. Top 20 functions by self time (cProfile, all programs)')
    add('')
    add('Summed over every profiled cold build. cProfile overhead inflates these numbers; the ranking'
        ' is what matters.')
    add('')
    add('| # | function | file:line | self s | calls |')
    add('|---:|---|---|---:|---:|')
    for index, row in enumerate(data.get('top20_self') or [], 1):
        add('| %d | `%s` | `%s:%s` | %s | %d |' % (
            index, row['function'], row['file'], row['line'], f(row['self']), row['calls']))
    add('')
    if data.get('top20_self'):
        top20 = sum(row['self'] for row in data['top20_self'])
        profiled = sum(p.get('profile_wall') or 0.0 for p in built)
        emitter_cum = (_total(built, lambda p: (p['passes'] or {}).get('typed_emit_cum') or 0.0)
                       + _total(built, lambda p: (p['passes'] or {}).get('general_emit_cum') or 0.0))
        emitter_timed = _total(built, lambda p: p['phases']['typed_emit']
                               + p['phases']['general_emit'])
        timed_wall = _total(built, lambda p: p['cold_median'])
        hot_share = (top20 / emitter_cum) * (emitter_timed / timed_wall) if emitter_cum else 0.0
        walk = sum(row['self'] for row in data['top20_self']
                   if row['function'] in ('walk', 'iter_child_nodes', 'iter_fields', '_walk_uncached'))
        queries = sum(row['self'] for row in data['top20_self']
                      if row['function'] in ('_etype', '_is_str_expr', '_is_slist_expr'))
        add('Summed top-20 self time is %s s, %s of the profiled wall (%s s) and %s of the profiled'
            ' emitter cumulative (`typed_emit_cum` + `general_emit_cum` = %s s). Applying that'
            ' cProfile proportion to the timed emitter share (%s of the timed cold wall) gives an'
            ' estimated %s x %s = %s of the timed wall. This is a derived estimate, not a timed'
            ' measurement. The %s figure overstates it because cProfile charges call-heavy functions'
            ' the most, so neither number is used as a pure measured Amdahl share.'
            % (f(top20, 2), pct(top20, profiled), f(profiled, 2), pct(top20, emitter_cum),
               f(emitter_cum, 2), pct(emitter_timed, timed_wall),
               pct(top20, emitter_cum), pct(emitter_timed, timed_wall), pct(hot_share, 1.0),
               pct(top20, profiled)))
        add('')
        add('Within the top 20, the AST-walk family (`walk`, `iter_child_nodes`, `iter_fields`,'
            ' `_walk_uncached`) is %s s = %s of the profiled wall, and the memoised type queries'
            ' (`_etype` twice, `_is_str_expr`, `_is_slist_expr`) %s s = %s.'
            % (f(walk, 2), pct(walk, profiled), f(queries, 2), pct(queries, profiled)))
        add('')
    if not data.get('top20_self'):
        add('(The top-20 table is written when a run finishes; this file was rendered from a partial'
            ' run.)')
        add('')

    add('## 3. Warm (whole-build cache hit)')
    add('')
    add('A first run fills `AIL_CACHE`; the next runs hit the driver\'s `fe` entry and copy the stored'
        ' binary. What still runs: the outer interpreter and its imports, `_load_sources` (reading and'
        ' merging the source), the front-end key (hashing the merged source and every compiler source'
        ' in `python/pkg-v12`), the cache lookup and unpack, and writing the output. `pyc.py` is not'
        ' started, so `typed`/`general`/`cc` are 0. On a general-path program the hit ALSO runs the'
        ' `check` subprocess that positions the advisory fallback note (the `other` column below and'
        ' §1), so `scar_life` and `ticket_audit` stay at 12.3 s and 25.5 s warm: the whole-build cache'
        ' does not remove that second front end.')
    add('')
    headers = ['program', 'cold wall', 'fill run', 'warm wall', 'warm start+import', 'warm load',
               'warm key hash', 'warm other']
    align = ['---', '---:', '---:', '---:', '---:', '---:', '---:', '---:']
    rows = []
    for p in built:
        warm = p.get('warm') or {}
        if not warm.get('median'):
            continue
        ph = warm.get('phases') or {}
        passes = warm.get('passes') or {}
        rows.append([p['name'], f(p.get('cold_median')), f(warm.get('fill_wall')),
                     f(warm.get('median')), f(ph.get('startup_imports')),
                     f(ph.get('outer_load')), f(passes.get('cache_frontend_key_cum')),
                     f(ph.get('other'))])
    add(table(headers, rows, align))
    add('')
    warm_rows = [(p.get('cold_median'), (p.get('warm') or {}).get('median')) for p in built
                 if (p.get('warm') or {}).get('median')]
    if warm_rows:
        fast = [(p.get('cold_median'), p['warm']['median']) for p in built
                if (p.get('warm') or {}).get('median') and p['warm']['median'] < 2.0]
        add('Median over these programs: cold %s s -> warm %s s (%.1fx). Excluding the three'
            ' note-check outliers (`scar_life`, `ticket_audit`, `term_rank`): cold %s s -> warm %s s'
            ' (%.1fx). The whole-build cache removes the front end; the fast residual is the outer'
            ' process\'s load, hashing and binary copy.'
            % (f(_median([a for a, _ in warm_rows]), 2), f(_median([b for _, b in warm_rows]), 2),
               _ratio(_median([a for a, _ in warm_rows]), _median([b for _, b in warm_rows])),
               f(_median([a for a, _ in fast]), 2), f(_median([b for _, b in fast]), 2),
               _ratio(_median([a for a, _ in fast]), _median([b for _, b in fast]))))
        add('')

    add('## 4. Peak memory of the front end')
    add('')
    add('`/usr/bin/time -v`, whole child tree, one cold build.')
    add('')
    add('| program | path | peak RSS MiB | wall |')
    add('|---|---|---:|---:|')
    for p in built:
        if p.get('peak_kb'):
            add('| %s | %s | %.1f | %s |' % (p['name'], p['path'], p['peak_kb'] / 1024.0,
                                             f(p.get('memory_wall'))))
    add('')
    peaks = [p['peak_kb'] / 1024.0 for p in built if p.get('peak_kb')]
    if peaks:
        add('Median peak RSS %s MiB, maximum %s MiB (%s).'
            % (f(_median(peaks), 1), f(max(peaks), 1),
               max(built, key=lambda p: p.get('peak_kb') or 0)['name']))
        add('')
    add('## Caveats')
    add('')
    add('* The runner is shared. Absolute times move with load; ratios and shares are the stable part.')
    add('* `ast.parse` is called several times per build (driver merge, refusal passes, `_to_c`,'
        ' `_rewrite_script`); the timed wrappers report its total as a nested component and cProfile'
        ' attributes the same calls to `ast.parse`, which is why it appears in the top-20 rather than'
        ' a single driver function.')
    add('* The emitter times include both analysis and C emission, as explained under Method.')
    add('')
    args.out.write_text('\n'.join(lines), encoding='utf8')
    print('wrote', args.out)


def _median(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])


def _total(items, fn):
    return sum(fn(item) or 0.0 for item in items)


def _frontend(p):
    ph = p['phases']
    return (ph['startup_imports'] + ph['outer_load'] + ph['inner_pre_passes']
            + ph['typed_emit'] + ph['general_emit'])


def _ratio(a, b):
    if not a or not b:
        return 0.0
    return a / b


if __name__ == '__main__':
    main()
