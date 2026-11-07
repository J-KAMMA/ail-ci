#!/usr/bin/env python3
"""Measure the upper bound of each emitter defect by hand-editing the generated C.

Each patch under lab/emit/patches removes one emitted construct from a copy of
the generated C.  The script rebuilds that copy, runs the same callgrind input as
analyze.py, checks stdout is byte-identical to the C baseline, and writes the
before/after Ir.  A patch is evidence for an *upper bound*: it says what the
instruction stream would cost if the emitter stopped producing that construct,
not that the compiler can elide it without analysis.

    python3 lab/emit/bounds.py                       # all variants
    python3 lab/emit/bounds.py --only ledger_bin_noovf
    python3 lab/emit/bounds.py --work /tmp/emit-bounds

valgrind and patch(1) must be on PATH.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402
from analyze import TOTAL  # noqa: E402

PATCHES = HERE / 'patches'
DESCRIPTIONS = {
    'echo_pack_dict2': ('Replace the ail_idict chain with four parallel arrays (head/prev/key) '
                        'and sp_find; emit the chain link directly', 'ail_idict_has/need/get/put per packet key'),
    'tally_lang_norec': ('Drop the per-call `if (ail_d > AIL_MAX_RECURSION_DEPTH)` from ev__d',
                         'one compare+branch per ev__d call'),
    'ledger_bin_noovf': ('readvar: ck_add/ck_mul/ck_shl/ck_add -> plain C operators',
                         'four overflow-checked operations per varint byte'),
    'ticket_audit_noovf_int': ('ail_bytes_to_int: drop the per-digit (limit-d)/10 test',
                               'divide + compare + branch per input digit'),
    'ticket_audit_noview': ('40 constant-index ail_blist_view calls -> B->p[i]',
                            'bounds check + call per ticket field'),
    'ticket_audit_nometa': ('ail_blist_meta body -> (void)B (the invariant test)',
                            'six-compare invariant test on every list operation'),
    'tree_fold_nobget': ('parse_tree: ail_bytes_get(v_data, pos) -> v_data.p[pos]',
                         'bounds check + call per parsed byte'),
    'tree_fold_nopop': ('ail_list_pop -> --n / p[--n] in the worklist',
                        'call + empty test per stack pop'),
    'tree_fold_nospan': ('20 ail_list_span_get(v_*, i) -> (v_*)->f_*.p[i]',
                         'call + bounds test per tree node'),
    'echo_pack_pushloop': ('list push init loop -> direct length/reserve/index writes',
                           'call + capacity test per initialized element'),
    'echo_pack_nobounds': ('ail_bytes_get + ail_ir_view_get -> direct p[i]',
                           'two bounds-checked accessors per packed byte'),
    'echo_pack_cmpmatch': ('Collapse the nested byte-compare loops into one while',
                           'loop bookkeeping and repeated bounds tests per compared byte'),
    'echo_pack_ai_append': ('always_inline ail_bytearray_append',
                            'append call overhead only (negative result)'),
    'berth_sim_noascii': ('stdin_readline: skip the per-line ASCII scan (force _ascii=1)',
                          'UTF-8/ASCII classification pass per input line'),
}


def run(binary, case):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run([str(binary)] + case['args'], stdin=stdin,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600)
    finally:
        if case['stdin']:
            stdin.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--tasks', default=','.join(analyze.TASKS))
    ap.add_argument('--work', default='/tmp/ail-emit-bounds')
    ap.add_argument('--out', default=str(HERE / 'data' / 'bounds.json'))
    args = ap.parse_args()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(',')) if args.only else None
    out = {'method': {'tool': 'callgrind Ir only', 'ail_cflags': analyze.AIL_CFLAGS,
                      'c_cflags': analyze.C_CFLAGS, 'edits': 'lab/emit/patches/*.diff'},
           'bounds': []}
    for task in args.tasks.split(','):
        csrc, exe, cexe = analyze.build(task, work)
        case = analyze.attrib.case(task, work)
        cg = work / (task + '_base.cg')
        p = analyze.callgrind(exe, case, cg, dict(os.environ))
        total = int(TOTAL.search(subprocess.run(
            ['callgrind_annotate', '--show=Ir', str(cg)], capture_output=True, text=True).stdout
        ).group(1).replace(',', ''))
        cbase = run(cexe, case)
        print('%-13s baseline %s' % (task, format(total, ',')), flush=True)
        patches = sorted(PATCHES.glob(task + '_*.diff'))
        for patch in patches:
            name = patch.stem
            if wanted is not None and name not in wanted:
                continue
            vdir = work / ('v_' + name)
            if vdir.exists():
                shutil.rmtree(vdir)
            vdir.mkdir()
            src = vdir / 'program.c'
            shutil.copy2(csrc, src)
            r = subprocess.run(['patch', '-p1', '-s', '-i', str(patch)], cwd=vdir,
                               capture_output=True, text=True)
            if r.returncode:
                raise SystemExit('%s: patch failed\n%s' % (name, r.stdout + r.stderr))
            vexe = vdir / 'prog'
            r = subprocess.run(['gcc'] + analyze.AIL_CFLAGS + ['-o', str(vexe), str(src), '-lm'],
                               capture_output=True, text=True)
            if r.returncode:
                raise SystemExit('%s: gcc failed\n%s' % (name, r.stderr[-2000:]))
            vcg = vdir / 'callgrind.out'
            vp = analyze.callgrind(vexe, case, vcg, dict(os.environ))
            same = vp.stdout == cbase.stdout
            if not same:
                raise SystemExit('%s: stdout differs from the C baseline' % name)
            after = int(TOTAL.search(subprocess.run(
                ['callgrind_annotate', '--show=Ir', str(vcg)], capture_output=True, text=True).stdout
            ).group(1).replace(',', ''))
            saved = total - after
            desc, target = DESCRIPTIONS[name]
            rec = {'task': task, 'variant': name, 'edit': desc, 'target': target,
                   'before': total, 'after': after, 'saved': saved,
                   'stdout_same': same}
            out['bounds'].append(rec)
            print('  %-24s %15s -> %15s  saved %13s' %
                  (name, format(total, ','), format(after, ','), format(saved, ',')), flush=True)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + '\n')
    print('wrote', dest)


if __name__ == '__main__':
    main()
