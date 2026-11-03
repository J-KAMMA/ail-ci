#!/usr/bin/env python3
"""Bounds/recursion-check census and the BCE no-regression check for the ten compare-lab tasks.

  python3 lab/beatc/bce_census.py census [--tasks a,b] [--icount perf|callgrind] --out /tmp/census.json
      icount of the AIL build with (base) and without the index checks (nobounds), the recursion-depth
      bookkeeping (nodepth), and both (neither) -- the generated C is edited by regex, as SPEC1 did; every
      variant must print the same bytes and exit code as base (an upper bound, not a legal build).
  python3 lab/beatc/bce_census.py check --base /path/to/base-tree [--tasks ...] [--icount ...] --out f.json
      builds every task's main.ail (and main.py with --syntax python) in the base tree and in this tree;
      tasks whose generated C is byte-identical are "same"; the others are measured (icount, stripped bytes,
      output equal to base). Exit 1 if any changed task has a higher icount or a different output.

icount: tools/icount.c via perf_event when it works, else `valgrind --tool=callgrind` (slow: 50-100x).
scar_life's perf input is ~3.6e11 instructions: under callgrind it runs on the public[0] input instead.
"""
import argparse, hashlib, importlib.util, json, os, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
TASKS = ['berth_sim', 'chain_relax', 'echo_pack', 'ledger_bin', 'rail_transfer', 'scar_life', 'tally_lang',
         'term_rank', 'ticket_audit', 'tree_fold']
CHK_A = re.compile(r'__builtin_expect\(\(uint64_t\)\s*([\w>\-\.]+)\s*>=\s*\(uint64_t\)\s*([\w>\-\.]+),\s*0\)')
CHK_B = re.compile(r'__builtin_expect\(!\(\(uint64_t\)\s*([\w>\-\.]+)\s*<\s*\(uint64_t\)\s*([\w>\-\.]+)\),\s*0\)')
CHK_C = re.compile(r'__builtin_expect\(\(uint64_t\)\((\w+)\) < \(uint64_t\)\((\w+)\), 1\)')
NUMF = '__builtin_expect(s && (uint64_t)i < (uint64_t)s->n, 1)'
BYTEARRAY = '__builtin_expect(B && B->refs && (uint64_t)index < (uint64_t)B->n, 1)'
DEPTH_IN = re.compile(r'^\s*if \(\+\+ail_depth > AIL_MAX_RECURSION_DEPTH\) ail_die\("recursion depth exceeded"\);\s*$')
DEPTH_OUT = re.compile(r'^\s*ail_depth--;\s*$')


def load_cases(task, small=False):
    spec = importlib.util.spec_from_file_location('gen_' + task, REPO / 'lab/compare/tasks' / task / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    public, hidden, perf = m.cases(random.Random('%s-20261012' % task))
    name, data, args = public[0] if small else perf
    p = Path(tempfile.gettempdir()) / ('bce_in_%s_%d.bin' % (task, small))
    p.write_bytes(data)
    return dict(stdin=bool(getattr(m, 'STDIN', False)), path=str(p), args=[a.replace('{input}', str(p)) for a in args])


def _run(cmd, case, env=None):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run(cmd + case['args'], stdin=stdin, capture_output=True, env=env, timeout=3600)
    finally:
        if case['stdin']:
            stdin.close()


def output(exe, case):
    r = _run([str(exe)], case)
    return r.returncode, hashlib.sha256(r.stdout).hexdigest()


def icount(exe, case, mode):
    if mode == 'perf':
        tool = Path(tempfile.gettempdir()) / 'bce_icount'
        if not tool.exists():
            subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(tool),
                            str(REPO / 'tools/icount.c')], check=True)
        r = _run([str(tool), str(exe)], case)
        return int(r.stdout.split()[-1]) if r.returncode == 0 and r.stdout.strip() else None
    r = _run(['valgrind', '--tool=callgrind', '--callgrind-out-file=/dev/null', str(exe)], case)
    m = re.search(rb'Collected : (\d+)', r.stderr)
    return int(m.group(1)) if m else None


def pick_mode(mode):
    if mode != 'auto':
        return mode
    tool = Path(tempfile.gettempdir()) / 'bce_icount'
    if not tool.exists():
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(tool),
                        str(REPO / 'tools/icount.c')], check=True)
    r = subprocess.run([str(tool), '/bin/true'], capture_output=True)
    return 'perf' if r.returncode == 0 else 'callgrind'


def compile_task(tree, task, work, syntax='ail'):
    """Build with --debug-dir; return (program.c text, gcc command, binary path, native report) or raise."""
    src = Path(tree) / 'lab/compare/src' / task / ('main.ail' if syntax == 'ail' else 'main.py')
    dbg = work / ('dbg_%s_%s' % (task, syntax))
    shutil.rmtree(dbg, ignore_errors=True)
    exe = work / ('%s_%s.bin' % (task, syntax))
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), AIL_NO_CACHE='1')
    (work / 'tmp').mkdir(exist_ok=True)
    cmd = [sys.executable, '-B', str(Path(tree) / 'AIL_CURRENT/ail_chatgpt.py'), 'compile', str(src), '-o', str(exe),
           '--debug-dir', str(dbg)]
    if syntax == 'python':
        cmd[5:5] = ['--syntax', 'python'] + (['--exact-int'] if task in ('rail_transfer', 'chain_relax') else [])
    r = subprocess.run(cmd, capture_output=True, env=env)
    if r.returncode:
        raise RuntimeError('build failed: ' + r.stderr.decode('utf8', 'replace')[-800:])
    rep = json.load(open(dbg / 'native_report.json'))
    return (dbg / 'program.c').read_text(), rep['operations'][-1]['command'], exe, rep


def gcc(cmd, csrc, out):
    c = list(cmd)
    c[c.index('-o') + 1] = str(out)
    c[max(k for k, x in enumerate(c) if x.endswith('.c'))] = str(csrc)
    r = subprocess.run(c, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-1500:])


def user_lines(rep):
    s = set()
    for g in rep['generated']:
        for f in g.get('functions', []):
            s.update(range(f['c_line_start'] - 1, f['c_line_end']))
    return s


def edit(src, bounds, depth, user):
    out = []
    for k, ln in enumerate(src.split('\n')):
        if bounds:
            ln = CHK_C.sub('1', CHK_B.sub('0', CHK_A.sub('0', ln)))
            ln = ln.replace(NUMF, '__builtin_expect(s != 0, 1)').replace(BYTEARRAY, '__builtin_expect(B && B->refs, 1)')
        if depth and k in user and (DEPTH_IN.match(ln) or DEPTH_OUT.match(ln)):
            ln = ''
        out.append(ln)
    return '\n'.join(out)


def stripped(exe, work):
    t = work / 'strip.tmp'
    shutil.copy(exe, t)
    subprocess.run(['strip', str(t)], capture_output=True)
    return os.path.getsize(t)


def census(args, mode, work):
    res = {}
    for task in args.tasks:
        small = mode == 'callgrind' and task == 'scar_life'
        case = load_cases(task, small)
        src, cmd, exe, rep = compile_task(REPO, task, work)
        user = user_lines(rep)
        rec, ref = dict(input='public0' if small else 'perf'), None
        for name, b, d in (('base', 0, 0), ('nobounds', 1, 0), ('nodepth', 0, 1), ('neither', 1, 1)):
            cs = work / ('v_%s_%s.c' % (task, name))
            cs.write_text(edit(src, b, d, user))
            ve = work / ('v_%s_%s' % (task, name))
            gcc(cmd, cs, ve)
            out = output(ve, case)
            ref = ref or out
            rec[name] = dict(icount=icount(ve, case, mode), same_output=out == ref)
        b = rec['base']['icount']
        for name in ('nobounds', 'nodepth', 'neither'):
            if b and rec[name]['icount']:
                rec[name]['share'] = round(1 - rec[name]['icount'] / b, 4)
        res[task] = rec
        print(task, {k: rec[k].get('share') for k in ('nobounds', 'nodepth', 'neither')},
              'same', all(rec[k]['same_output'] for k in ('nobounds', 'nodepth', 'neither')), flush=True)
    return res, 0


def check(args, mode, work):
    res, bad = {}, 0
    for task in args.tasks:
        for syntax in ('ail', 'python'):
            key = '%s/%s' % (task, syntax)
            try:
                bw, hw = work / 'base', work / 'head'
                bw.mkdir(exist_ok=True); hw.mkdir(exist_ok=True)
                bsrc, _, bexe, _ = compile_task(args.base, task, bw, syntax)
                hsrc, _, hexe, _ = compile_task(REPO, task, hw, syntax)
            except Exception as e:
                res[key] = dict(error=str(e)[:400]); print(key, 'ERROR', str(e)[:200]); bad = 1
                continue
            if bsrc == hsrc:
                res[key] = dict(same_c=True); print(key, 'same C', flush=True)
                continue
            small = mode == 'callgrind' and task == 'scar_life'
            case = load_cases(task, small)
            bo, ho = output(bexe, case), output(hexe, case)
            bi, hi = icount(bexe, case, mode), icount(hexe, case, mode)
            rec = dict(same_c=False, same_output=bo == ho, icount_base=bi, icount_head=hi,
                       ratio=round(hi / bi, 5) if bi and hi else None,
                       stripped_base=stripped(bexe, work), stripped_head=stripped(hexe, work))
            res[key] = rec
            if not rec['same_output'] or not bi or not hi or hi > bi:
                bad = 1
            print(key, rec, flush=True)
    return res, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['census', 'check'])
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--icount', default='auto', choices=['auto', 'perf', 'callgrind'])
    ap.add_argument('--base', help='base tree (check)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    args.tasks = [t for t in args.tasks.split(',') if t]
    mode = pick_mode(args.icount)
    with tempfile.TemporaryDirectory(prefix='bce-') as tmp:
        res, bad = (census if args.cmd == 'census' else check)(args, mode, Path(tmp))
    json.dump(dict(icount=mode, tasks=res), open(args.out, 'w'), indent=1)
    sys.exit(bad)


if __name__ == '__main__':
    main()
