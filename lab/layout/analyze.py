#!/usr/bin/env python3
"""layout: turn data/layout.json into the tables and the ranking in RESULTS.md.

    python3 lab/layout/analyze.py            # reads data/layout.json, writes data/analysis.json
    python3 lab/layout/analyze.py --print    # ... and prints the markdown tables

Per task it reports, for AIL and C, the counters and the share of LLC misses each data structure
(an emitted `f_<field>` struct column, a named runtime container, or the emitted function a line
sits in) is charged. For each hand edit it reports the measured deltas and the Amdahl bound:
  share     = delta LLC / AIL baseline LLC      (how much of the gap the edit removes)
  amdahl    = delta LLC / (AIL baseline LLC - C LLC)   (how much of the *excess* it removes)
and the same for instructions and wall time where measured.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
TASKS = ['tree_fold', 'berth_sim', 'ticket_audit', 'echo_pack', 'ledger_bin']


def pct(a, b):
    return 100.0 * a / b if b else float('nan')


def delta(x, y):
    return None if x is None or y is None else y - x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--print', action='store_true')
    ap.add_argument('--json', default=str(DATA / 'analysis.json'))
    args = ap.parse_args()
    rows = json.loads((DATA / 'layout.json').read_text())
    out = {}

    for task in TASKS:
        row = rows.get(task)
        if not row or 'builds' not in row:
            continue
        b = row['builds']
        ail, c = b['ail'], b['c']
        rec = dict(task=task, input_bytes=row['input_bytes'],
                   ail=ail['counts'], c=c['counts'],
                   ail_wall=ail['wall'], c_wall=c['wall'],
                   ail_bytes=ail['bytes'], c_bytes=c['bytes'],
                   ail_classes=ail['classes'], c_classes=c['classes'],
                   ratio=dict(
                       instructions=ail['counts']['instructions'] / c['counts']['instructions'],
                       llc=ail['counts']['ll_misses'] / c['counts']['ll_misses'],
                       d1=ail['counts']['d1_misses'] / c['counts']['d1_misses'],
                       wall=ail['wall']['best_s'] / c['wall']['best_s']),
                   variants={})
        for label, v in b.items():
            if label in ('ail', 'c'):
                continue
            if not v.get('counts'):
                continue
            excess_llc = ail['counts']['ll_misses'] - c['counts']['ll_misses']
            excess_ir = ail['counts']['instructions'] - c['counts']['instructions']
            d_llc = v['counts']['ll_misses'] - ail['counts']['ll_misses']
            d_ir = v['counts']['instructions'] - ail['counts']['instructions']
            rec['variants'][label] = dict(
                ok=v['ok'], counts=v['counts'], wall=v['wall'], bytes=v['bytes'],
                d_llc=d_llc, d_ir=d_ir,
                d_llc_pct_of_ail=pct(-d_llc, ail['counts']['ll_misses']),
                d_llc_pct_of_excess=pct(-d_llc, excess_llc),
                d_ir_pct_of_excess=pct(-d_ir, excess_ir),
                d_wall_ms=None if not v['wall'].get('best_s') else
                1000.0 * (v['wall']['best_s'] - ail['wall']['best_s']),
                d_wall_pct=pct(-(v['wall']['best_s'] - ail['wall']['best_s']), ail['wall']['best_s']),
                d_bytes=v['bytes'] - ail['bytes'],
                d_rss_kib=(None if v['wall'].get('rss_kib') is None or ail['wall'].get('rss_kib') is None
                           else v['wall']['rss_kib'] - ail['wall']['rss_kib']),
                classes=v['classes'])
        out[task] = rec

    Path(args.json).write_text(json.dumps(out, indent=1) + '\n')

    if args.print:
        print('## Counters\n')
        print('| task | build | instructions | D1 misses | LLC misses | LLC read | LLC write | wall best s | RSS KiB | exe B |')
        print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
        for t in TASKS:
            if t not in out:
                continue
            for name, key in (('AIL typed', 'ail'), ('C', 'c')):
                r = out[t]
                cnt = r[key]
                w = r['ail_wall'] if key == 'ail' else r['c_wall']
                sz = r['ail_bytes'] if key == 'ail' else r['c_bytes']
                print('| %s | %s | %d | %d | %d | %s | %s | %.3f | %s | %d |' % (
                    t, name, cnt['instructions'], cnt['d1_misses'], cnt['ll_misses'],
                    cnt.get('ll_read'), cnt.get('ll_write'), w['best_s'],
                    w.get('rss_kib'), sz))
        print('\n## Hand edits\n')
        print('| task | edit | d instructions | d D1 | d LLC | % of AIL LLC | % of excess LLC | d wall ms | d RSS KiB | d exe B | stdout |')
        print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|')
        for t in TASKS:
            if t not in out:
                continue
            for label, v in out[t]['variants'].items():
                print('| %s | %s | %+d | %+d | %+d | %.1f%% | %.1f%% | %+.1f | %s | %+d | %s |' % (
                    t, label, v['d_ir'],
                    v['counts']['d1_misses'] - out[t]['ail']['d1_misses'], v['d_llc'],
                    v['d_llc_pct_of_ail'], v['d_llc_pct_of_excess'],
                    v['d_wall_ms'] or 0.0, v['d_rss_kib'], v['d_bytes'],
                    'identical' if v['ok'] else 'MISMATCH'))
        print('\n## LLC misses by data structure (AIL)\n')
        for t in TASKS:
            if t not in out:
                continue
            print('\n### %s\n' % t)
            print('| data structure | instructions | LLC read misses | LLC write misses |')
            print('|---|---:|---:|---:|')
            cl = out[t]['ail_classes']
            tot = sum(v['DLmr'] + v['DLmw'] for v in cl.values())
            for k, v in sorted(cl.items(), key=lambda kv: -(kv[1]['DLmr'] + kv[1]['DLmw']))[:14]:
                if v['DLmr'] + v['DLmw'] < 0.001 * max(tot, 1):
                    continue
                print('| %s | %d | %d | %d |' % (k, v['Ir'], v['DLmr'], v['DLmw']))
            print('\nC, same view:\n')
            print('| data structure | instructions | LLC read misses | LLC write misses |')
            print('|---|---:|---:|---:|')
            cl = out[t]['c_classes']
            tot = sum(v['DLmr'] + v['DLmw'] for v in cl.values())
            for k, v in sorted(cl.items(), key=lambda kv: -(kv[1]['DLmr'] + kv[1]['DLmw']))[:10]:
                if v['DLmr'] + v['DLmw'] < 0.001 * max(tot, 1):
                    continue
                print('| %s | %d | %d | %d |' % (k, v['Ir'], v['DLmr'], v['DLmw']))


if __name__ == '__main__':
    main()
