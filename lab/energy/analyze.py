#!/usr/bin/env python3
"""Turn lab/energy/data/energy.json into the RESULTS.md table and the avoidable-energy split.

    python3 lab/energy/analyze.py [--energy PATH] [--attrib PATH]

The avoidable-energy split reuses roof1's line attribution (`lab/roof/data/attrib/attrib.json`):
the AIL-minus-C instruction energy of the five attributed typed builds is divided by the measured
per-category Ir shares. The DRAM term (LLC misses x 64 B x E_dram) is reported separately, because
roof1's seven categories are source-line patterns, not memory traffic. Unattributed programs are
reported only as totals; nothing is invented for them.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer',
         'scar_life', 'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
LANGS = ['ail', 'ail-py', 'c', 'rust', 'python']
CATS = ['overflow', 'bounds', 'refcount', 'alloc/free', 'copies', 'boxing', 'other']


def fmt_j(x):
    return 'n/a' if x is None else '%.3e' % x


def fmt_ratio(x):
    return 'n/a' if x is None else '%.2f' % x


def fmt_floor(x):
    return 'n/a' if x is None else '%.2e' % x


def table(energy):
    print('| task | lang | source | instructions | LLC miss | J model (est.) | J measured | x C | x Rust | floor J | J/floor |')
    print('|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for task in TASKS:
        rows = energy.get(task, {})
        cj = (rows.get('c') or {}).get('j_model')
        rj = (rows.get('rust') or {}).get('j_model')
        for lang in LANGS:
            r = rows.get(lang) or {}
            if r.get('error'):
                print('| %s | %s | %s | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |  # %s'
                      % (task, lang, r.get('source', ''), r['error']))
                continue
            status = '' if r.get('build_ok') else ' (%s)' % r.get('icount_method', 'refused')
            ins = r.get('instructions')
            # A row with instructions but no LLC count has only the instruction term; it is not the
            # two-term model, so it is shown as n/a with a dagger and never used in a ratio.
            incomplete = ins is not None and r.get('llc_misses') is None
            jm = None if incomplete else r.get('j_model')
            print('| %s | %s%s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                task, lang, status, r.get('source') or '',
                'n/a' if ins is None else '%.3e' % ins,
                'n/a' if r.get('llc_misses') is None else '%.3e' % r['llc_misses'],
                'n/a †' if incomplete else fmt_j(jm), fmt_j(r.get('j_measured')),
                fmt_ratio(jm / cj if jm is not None and cj else None),
                fmt_ratio(jm / rj if jm is not None and rj else None),
                fmt_floor(r.get('landauer_floor')), fmt_floor(r.get('j_per_floor'))))


def avoidable(energy, attrib, e_instr, e_dram_byte):
    """AIL (typed.py) minus C, split by roof1's categories for the five attributed programs."""
    out = {}
    for task in TASKS:
        rows = energy.get(task, {})
        a, c = rows.get('ail') or {}, rows.get('c') or {}
        ai, ci = a.get('instructions'), c.get('instructions')
        al, cl = a.get('llc_misses'), c.get('llc_misses')
        if ai is None or ci is None:
            continue
        de_i = (ai - ci) * e_instr
        de_m = None if al is None or cl is None else (al - cl) * 64 * e_dram_byte
        rec = dict(instr_delta=ai - ci, instr_j=de_i, dram_j=de_m,
                   total_j=de_i + de_m if de_m is not None else None, attributed=False)
        att = attrib.get(task)
        if att:
            d = att.get('delta') or {}
            total = d.get('total')
            if total:
                cat = dict(d.get('by_category') or {})
                cat['other'] = d.get('other', 0)
                rec['attributed'] = True
                rec['categories'] = {k: de_i * cat.get(k, 0) / total for k in CATS}
        out[task] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--energy', default=str(HERE / 'data' / 'energy.json'))
    ap.add_argument('--attrib', default=str(REPO / 'lab' / 'roof' / 'data' / 'attrib' / 'attrib.json'))
    args = ap.parse_args()
    energy = json.loads(Path(args.energy).read_text())
    meta = energy.pop('_meta', {})
    attrib = json.loads(Path(args.attrib).read_text()) if Path(args.attrib).is_file() else {}
    extra = HERE / 'data' / 'attrib_extra.json'
    if extra.is_file():
        attrib.update(json.loads(extra.read_text()))
    table(energy)
    av = avoidable(energy, attrib, meta.get('e_instr_j', 0.1e-12), meta.get('e_dram_byte_j', 160e-12))
    print('\n## avoidable (editable table)')
    print('| task | d instructions | d instr J | d DRAM J | d total J | split |')
    print('|---|---:|---:|---:|---:|---|')
    sums = {k: 0.0 for k in CATS}
    for task in TASKS:
        r = av.get(task)
        if not r:
            continue
        if r['attributed']:
            cells = ', '.join('%s %.2e' % (k, v) for k, v in sorted(r['categories'].items(), key=lambda kv: -kv[1]) if abs(v) > 0)
            for k, v in r['categories'].items():
                sums[k] += v
        else:
            cells = 'not attributed (only the total is measured)'
        print('| %s | %+.3e | %+.3e | %s | %s | %s |' % (
            task, r['instr_delta'], r['instr_j'], 'n/a' if r['dram_j'] is None else '%+.3e' % r['dram_j'],
            'n/a' if r['total_j'] is None else '%+.3e' % r['total_j'], cells))
    print('\n### signed sum over the attributed typed builds')
    for k, v in sorted(sums.items(), key=lambda kv: -kv[1]):
        print('- %s: %.3e J' % (k, v))
    extras = []
    for task in TASKS:
        rows = energy.get(task, {})
        a, c = rows.get('ail-py') or {}, rows.get('c') or {}
        ai, ci = a.get('instructions'), c.get('instructions')
        if ai is not None and ci is not None:
            al, cl = a.get('llc_misses'), c.get('llc_misses')
            de_i = (ai - ci) * meta.get('e_instr_j', 0.1e-12)
            de_m = None if al is None or cl is None else (al - cl) * 64 * meta.get('e_dram_byte_j', 160e-12)
            extras.append((task, de_i, de_m, de_i + de_m if de_m is not None else None))
    print('\n### main.py (general/typed as built) minus C, total only')
    for task, de_i, de_m, total in extras:
        print('- %s: instr %+.3e J, DRAM %s, total %s' % (
            task, de_i, 'n/a' if de_m is None else '%+.3e J' % de_m, 'n/a' if total is None else '%+.3e J' % total))
    json.dump(dict(avoidable=av, category_sum=sums,
                   main_py=[dict(task=t, instr_j=i, dram_j=m, total_j=x) for t, i, m, x in extras]),
              open(HERE / 'data' / 'analysis.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
