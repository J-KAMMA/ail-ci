#!/usr/bin/env python3
"""Vectorisation survey of the emitted C for all ten compare programs, for both AIL columns.

    python3 lab/roof/vec.py --out lab/roof/data/vec.json

For each AIL source (`typed.py`, compare-lab's `ail` column, and `main.py`, its `ail-py` column) it
records the loop counts from `gcc -fopt-info-vec-all` (the flag the task names) and, from
`objdump -d` of the emitted binary, the share of instructions that use an xmm/ymm register.  The
loop counts answer "how much of the hot code is vectorised"; the mnemonic share shows the residual
SIMD moves the compiler emits outside vectorised loops.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import attrib  # noqa: E402

TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer', 'scar_life',
         'tally_lang', 'term_rank', 'ticket_audit', 'tree_fold']
SOURCES = {'ail': 'typed.py', 'ail-py': 'main.py'}


def binary_simd(exe):
    p = subprocess.run(['objdump', '-d', str(exe)], capture_output=True, text=True)
    total = vec = 0
    for line in p.stdout.splitlines():
        m = re.match(r'^\s+[0-9a-f]+:\s+(?:[0-9a-f]{2} )+\s*\S+\s*(.*)$', line)
        if not m:
            continue
        total += 1
        if re.search(r'%[xyz]mm', m.group(1)):
            vec += 1
    return total, vec, (vec / total if total else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(HERE / 'data' / 'vec.json'))
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--langs', default=','.join(SOURCES))
    ap.add_argument('--merge', action='store_true',
                    help='update the existing vec.json instead of replacing it (keep other languages)')
    args = ap.parse_args()
    report = {}
    if args.merge and Path(args.out).is_file():
        try:
            report = json.loads(Path(args.out).read_text())
        except ValueError:
            report = {}
    langs = [l for l in args.langs.split(',') if l]
    with tempfile.TemporaryDirectory(prefix='vec-') as tmp:
        work = Path(tmp)
        for task in [t for t in args.tasks.split(',') if t]:
            report.setdefault(task, {})
            for lang in langs:
                src, exe = attrib.build_ail(task, work, SOURCES[lang], lang)
                if src is None or exe is None:
                    report[task][lang] = dict(source=SOURCES[lang], error='build failed')
                    continue
                rec = attrib.vec_report(src, exe, work, task + '_' + lang)
                total, vec, frac = binary_simd(exe)
                rec.update(source=SOURCES[lang], binary_instructions=total,
                           binary_simd_instructions=vec, binary_simd_share=round(frac, 4))
                report[task][lang] = rec
                print(task, lang, rec, flush=True)
            Path(args.out).write_text(json.dumps(report, indent=1) + '\n')
    Path(args.out).write_text(json.dumps(report, indent=1) + '\n')
    print('wrote', args.out)


if __name__ == '__main__':
    main()
