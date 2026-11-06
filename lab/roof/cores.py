#!/usr/bin/env python3
"""Cores used per compare program, measured as CPU time / wall (one run each).

    python3 lab/roof/cores.py --out lab/roof/data/cores.json

No hardware PMU is exposed here, so this is the direct measurement available for the "cores used"
column: /usr/bin/time reports user+sys CPU seconds for the child, and dividing by wall gives the
average number of cores busy.  A single-threaded program reads ~1.0.
"""
import argparse, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure  # noqa: E402

TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer', 'scar_life',
         'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'data' / 'cores.json'))
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--runs', type=int, default=2)
    args = ap.parse_args()
    rows = {}
    with tempfile.TemporaryDirectory(prefix='cores-') as tmp:
        work = Path(tmp)
        for task in [t for t in args.tasks.split(',') if t]:
            case = measure.make_case(task, work)
            row = {}
            for lang in ('c', 'ail'):
                out = work / ('%s_%s' % (task, lang))
                ok, _ = measure.build(task, lang, out)
                if not ok:
                    row[lang] = dict(error='build failed')
                    continue
                t = measure.time_runs(out, case, args.runs)
                row[lang] = dict(wall_s=round(t['wall_s'], 4), cpu_s=t['cpu_s'], cores=t['cores'])
            rows[task] = row
            print(task, row, flush=True)
            Path(args.out).write_text(json.dumps(rows, indent=1) + '\n')
    Path(args.out).write_text(json.dumps(rows, indent=1) + '\n')
    print('wrote', args.out)


if __name__ == '__main__':
    main()
