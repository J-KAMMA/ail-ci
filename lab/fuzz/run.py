#!/usr/bin/env python3
"""Differential runner: CPython versus AIL (default path and AIL_IR=1) over a seed range.

    python3 run.py --start 0 --count 50 --out fuzz-out [--jobs 1] [--modes default,ir]

Classes per (seed, mode):
  same       stdout and exit code equal
  refused    AIL named a compile-time refusal (compiler exit 3); counted, never a failure
  overflow   AIL raised OverflowError where CPython grew a big int; declared (64-bit int), its
             stdout must be a prefix of CPython's; counted, never a failure
  DIFF       a silent difference in stdout or exit code (a bug)
  crash      the compiler failed other than by refusal, or the binary died on a signal (a bug)
  timeout    the compiled program (or the compiler) hit the time limit; counted
  skipped    CPython itself timed out or produced too much output; the seed says nothing

Exit status 1 when any DIFF or crash occurred, else 0.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen  # noqa: E402

MODES = {'default': {}, 'ir': {'AIL_IR': '1'}}
CAP = 1 << 20  # bytes of output kept per stream


def run_proc(cmd, timeout, env=None, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=cwd)
        return r.returncode, r.stdout, r.stderr, False
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b'', e.stderr or b'', True


def text(b):
    return b[:CAP].decode('utf-8', 'replace')


def first_diff(a, b):
    al, bl = a.splitlines(), b.splitlines()
    for i in range(max(len(al), len(bl))):
        x = al[i] if i < len(al) else '<end>'
        y = bl[i] if i < len(bl) else '<end>'
        if x != y:
            return 'line %d: cpython=%r ail=%r' % (i + 1, x[:80], y[:80])
    return 'no line difference'


def classify(cpy, ail):
    c_rc, c_out, c_err, _ = cpy
    a_rc, a_out, a_err, a_to = ail
    if a_to:
        return 'timeout', 'run timed out'
    if a_rc is not None and (a_rc < 0 or a_rc >= 128):
        return 'crash', 'binary died with status %d' % a_rc
    if a_rc == c_rc and a_out == c_out:
        return 'same', ''
    if (((a_rc == 1) or (a_rc == 3 and b"limit: int_overflow" in a_err)) and (b"OverflowError" in a_err or b"overflow" in a_err.lower()) and c_out.startswith(a_out)):
        return 'overflow', 'AIL OverflowError, CPython rc=%s' % c_rc
    if a_rc != c_rc:
        return 'DIFF', 'exit code cpython=%s ail=%s; %s' % (c_rc, a_rc, first_diff(text(c_out), text(a_out)))
    return 'DIFF', first_diff(text(c_out), text(a_out))


def one_seed(seed, args, ail_py, modes):
    src = gen.generate(seed, args.off.split(','))
    work = Path(args.out) / 'work' / str(seed)
    work.mkdir(parents=True, exist_ok=True)
    py = work / 'prog.py'
    py.write_text(src, encoding='utf-8')
    ail_src = work / 'prog.ail'
    ail_src.write_text(src, encoding='utf-8')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONHASHSEED='0')
    env.pop('AIL_IR', None)
    cpy = run_proc([sys.executable, str(py)], args.timeout, env=env)
    results = []
    if cpy[3] or len(cpy[1]) > CAP:
        results.append({'seed': seed, 'mode': 'all', 'cls': 'skipped', 'reason': 'cpython timeout or oversized output'})
        shutil.rmtree(work, ignore_errors=True)
        return results
    for mode in modes:
        menv = dict(env, **MODES[mode])
        exe = work / ('exe-' + mode)
        t0 = time.time()
        crc, cout, cerr, cto = run_proc(
            [sys.executable, '-B', str(ail_py), 'compile', str(ail_src), '--syntax', 'python', '-o', str(exe)],
            args.compile_timeout, env=menv)
        rec = {'seed': seed, 'mode': mode, 'cpython_rc': cpy[0]}
        if cto:
            rec.update(cls='timeout', reason='compiler timed out')
            ail = None
        elif crc == 3:
            msg = (cerr or cout).decode('utf-8', 'replace').strip().splitlines()
            rec.update(cls='refused', reason=(msg[-1] if msg else '')[:200])
            ail = None
        elif crc != 0:
            msg = (cerr or cout).decode('utf-8', 'replace').strip().splitlines()
            errs = [l for l in msg if 'error' in l.lower()] or msg or ['']
            rec.update(cls='crash', reason='compiler rc=%s: %s' % (crc, errs[0].split('program.c:')[-1][:200]))
            ail = None
        else:
            ail = run_proc([str(exe)], args.timeout, env=menv)
            rec['ail_rc'] = ail[0]
            rec['cls'], rec['reason'] = classify(cpy, ail)
        rec['ms'] = int((time.time() - t0) * 1000)
        if rec['cls'] in ('DIFF', 'crash', 'timeout'):
            d = Path(args.out) / 'findings' / ('seed%d-%s-%s' % (seed, mode, rec['cls']))
            d.mkdir(parents=True, exist_ok=True)
            (d / 'prog.py').write_text(src, encoding='utf-8')
            (d / 'cpython.stdout').write_text(text(cpy[1]), encoding='utf-8')
            (d / 'cpython.stderr').write_text(text(cpy[2]), encoding='utf-8')
            if ail:
                (d / 'ail.stdout').write_text(text(ail[1]), encoding='utf-8')
                (d / 'ail.stderr').write_text(text(ail[2]), encoding='utf-8')
            else:
                (d / 'compile.stderr').write_text(text(cerr or cout), encoding='utf-8')
            (d / 'info.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')
            (d / 'reproduce.sh').write_text(
                '#!/bin/sh\n# from the repository root\npython3 lab/fuzz/gen.py %d%s -o prog.py\ncp prog.py prog.ail\n'
                '%spython3 AIL_CURRENT/ail_chatgpt.py compile prog.ail --syntax python -o prog_ail && ./prog_ail\n'
                'python3 prog.py\n' % (seed, (' --off ' + args.off) if args.off else '', ('AIL_IR=1 ' if mode == 'ir' else '')), encoding='utf-8')
        results.append(rec)
    shutil.rmtree(work, ignore_errors=True)
    return results


def summarize(records, args, modes, elapsed):
    cls_names = ['same', 'refused', 'overflow', 'DIFF', 'crash', 'timeout', 'skipped']
    done = sorted({r['seed'] for r in records})
    lines = ['## AIL differential fuzz: seeds %d..%d (%d run)' % (args.start, args.start + args.count - 1, len(done)), '',
             '| mode | ' + ' | '.join(cls_names) + ' |', '|---|' + '---|' * len(cls_names)]
    for mode in modes + ['all']:
        rs = [r for r in records if r['mode'] == mode]
        if rs or mode != 'all':
            lines.append('| %s | ' % mode + ' | '.join(str(sum(1 for r in rs if r['cls'] == c)) for c in cls_names) + ' |')
    bad = [r for r in records if r['cls'] in ('DIFF', 'crash')]
    lines += ['', 'Elapsed %.0f s. `refused` = named compile-time refusal (fine); `overflow` = declared 64-bit int '
              'difference (fine); `DIFF`/`crash` = findings.' % elapsed, '']
    if bad:
        lines += ['### Findings', '']
        for r in sorted(bad, key=lambda r: (r['seed'], r['mode']))[:50]:
            lines.append('- seed %d [%s] %s: %s' % (r['seed'], r['mode'], r['cls'], r['reason'][:200]))
        lines += ['', 'Programs and both outputs are in the `findings/` directory of the artifact.', '']
    why = {}
    for r in records:
        if r['cls'] == 'refused':
            key = r['reason'].split(':', 3)[-1].strip()[:110]
            why[key] = why.get(key, 0) + 1
    if why:
        lines += ['### Top refusal reasons', '']
        for k, v in sorted(why.items(), key=lambda kv: -kv[1])[:8]:
            lines.append('- %d x %s' % (v, k))
        lines.append('')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--count', type=int, default=50)
    ap.add_argument('--out', default='fuzz-out')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--off', default='', help='generator features to switch off: alias,listeq,stridx')
    ap.add_argument('--modes', default='default,ir')
    ap.add_argument('--timeout', type=float, default=10, help='seconds per program run')
    ap.add_argument('--compile-timeout', type=float, default=240)
    ap.add_argument('--budget', type=float, default=0, help='stop starting new seeds after this many seconds (0 = no limit)')
    ap.add_argument('--ail', default=str(HERE.parent.parent / 'AIL_CURRENT' / 'ail_chatgpt.py'))
    args = ap.parse_args()
    modes = args.modes.split(',')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    records = []
    seeds = range(args.start, args.start + args.count)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex, open(out / 'results.jsonl', 'w') as jl:
        def job(seed):
            if args.budget and time.time() - t0 > args.budget:
                return []
            return one_seed(seed, args, args.ail, modes)
        for rs in ex.map(job, seeds):
            for r in rs:
                records.append(r)
                jl.write(json.dumps(r) + '\n')
            jl.flush()
    shutil.rmtree(out / 'work', ignore_errors=True)
    md = summarize(records, args, modes, time.time() - t0)
    (out / 'summary.md').write_text(md, encoding='utf-8')
    print(md)
    return 1 if any(r['cls'] in ('DIFF', 'crash') for r in records) else 0


if __name__ == '__main__':
    sys.exit(main())
