#!/usr/bin/env python3
"""layout: where the memory AIL's typed build touches lives, and what a flat layout would save.

    python3 lab/layout/measure.py                 # all five programs, baseline AIL vs C
    python3 lab/layout/measure.py --tasks echo_pack
    python3 lab/layout/measure.py --variants      # also the hand-edited copies under edits/

For each task this emits the C AIL generates for `typed.py` (`compile --debug-dir`), rebuilds it
with the compiler's own flags, builds the hand-written `main.c` with `gcc -O2 -std=c11`, and runs
both on the task's perf input under valgrind cachegrind with the runner's cache geometry (L1d
32 KiB, L2 512 KiB, LLC 32 MiB), the same geometry lab/roof and lab/energy use. It records
instructions, D1 misses and LLC misses, per function and per emitted data structure (the `f_*`
field of a user struct, or the runtime container each line names), plus wall time (best of 5).

Every build's stdout must equal the task's CPython reference byte for byte, otherwise the row is
marked MISMATCH and is not used.

A variant is a `lab/layout/edits/<task>_<name>.diff` applied to a fresh copy of the emitted
`program.c` with `patch -p1`. That is the hand edit; nothing here changes the compiler.

Output: data/layout.json, data/cg/<task>_<build>.cg, data/annot/<task>_<build>.txt.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
GEN = REPO / 'lab' / 'compare' / 'tasks'
EDITS = HERE / 'edits'
DATA = HERE / 'data'
CG = DATA / 'cg'
ANNOT = DATA / 'annot'

TASKS = ['tree_fold', 'berth_sim', 'ticket_audit', 'echo_pack', 'ledger_bin']
# The compiler's own build flags (AIL_CURRENT/ail_native_build.py), so this is the shipped binary,
# plus -g so cg_annotate can map counts back to program.c. -g adds no instructions: the shipped
# non-g build of tree_fold and this one differ by 14 Ir out of 8.83e9.
AIL_CFLAGS = ['-O2', '-g', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
              '-Werror=implicit-function-declaration', '-Werror=implicit-int',
              '-Werror=incompatible-pointer-types', '-fno-asynchronous-unwind-tables']
C_CFLAGS = ['-O2', '-g', '-std=c11']
# The geometry lab/roof and lab/energy use, so the numbers are comparable across labs.
CACHEGRIND = ['valgrind', '--tool=cachegrind', '--cache-sim=yes', '--branch-sim=no',
              '--I1=32768,8,64', '--D1=32768,8,64', '--L2=524288,8,64', '--LL=33554432,16,64']
CG_SHOW = 'Ir,Dr,Dw,D1mr,D1mw,DLmr,DLmw'
NUM = re.compile(r'==\d+== ([A-Za-z0-9 ]+?):\s*([\d,]+)')
# a user struct field (`v_t->f_par`, `v_self->f_w`) or a runtime container name
FIELD = re.compile(r'->(f_\w+)\b')
RUNTIME = [('ail_idict', re.compile(r'ail_idict|ail_dict')),
           ('ail_tab', re.compile(r'ail_tab|ail_tab_hhas')),
           ('ail_pslist', re.compile(r'ail_pslist')),
           ('ail_slist', re.compile(r'ail_slist')),
           ('ail_list', re.compile(r'ail_list_\w+')),
           ('ail_sarena', re.compile(r'ail_sarena')),
           ('ail_barena', re.compile(r'ail_barena')),
           ('ail_bl', re.compile(r'ail_bl_\w+')),
           ('ail_str', re.compile(r'ail_str_\w+|format_i64')),
           ('ail_obj', re.compile(r'ail_obj_|ail_olist'))]


def case(name, work):
    spec = importlib.util.spec_from_file_location('g' + name, GEN / name / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _p, _h, perf = m.cases(random_seed(name))
    cname, data, args = perf
    path = work / (name + '.bin')
    path.write_bytes(data)
    return dict(name=cname, stdin=bool(getattr(m, 'STDIN', False)), path=path,
                args=[a.replace('{input}', str(path)) for a in args], bytes=len(data))


def random_seed(name):
    import random
    return random.Random('%s-20261012' % name)


def emit(task, work):
    """Return the emitted program.c for `typed.py`, built the way `compile` builds it."""
    dbg = work / (task + '.d')
    if dbg.exists():
        import shutil as _sh
        _sh.rmtree(dbg)
    out = work / (task + '_ail')
    p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(SRC / task / 'typed.py'),
                        '--syntax', 'python', '-o', str(out), '--debug-dir', str(dbg)],
                       capture_output=True, timeout=1800)
    if p.returncode != 0:
        raise SystemExit('%s: AIL compile failed\n%s' % (task, p.stderr.decode()[-3000:]))
    return dbg / 'program.c'


def gcc(src, out, flags):
    p = subprocess.run(['gcc'] + flags + ['-o', str(out), str(src), '-lm'],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit('gcc failed for %s\n%s' % (src, p.stderr[-3000:]))
    return out


def invoke(binary, c):
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run([str(binary)] + c['args'], stdin=stdin, capture_output=True,
                              timeout=1800)
    finally:
        if c['stdin']:
            stdin.close()


def reference(task, c, work):
    out = work / (task + '.ref')
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        with open(out, 'wb') as f:
            p = subprocess.run([sys.executable, str(GEN / task / 'reference.py')] + c['args'],
                               stdin=stdin, stdout=f, stderr=subprocess.PIPE, timeout=1800)
    finally:
        if c['stdin']:
            stdin.close()
    return p.returncode, out.read_bytes()


def run_cg(binary, c, cgfile):
    stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
    try:
        p = subprocess.run(CACHEGRIND + ['--cachegrind-out-file=' + str(cgfile), str(binary)] + c['args'],
                           stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=3000)
    finally:
        if c['stdin']:
            stdin.close()
    txt = p.stderr.decode('utf8', 'replace')
    got = {' '.join(m.group(1).split()): int(m.group(2).replace(',', '')) for m in NUM.finditer(txt)}
    if p.returncode != 0 or 'I refs' not in got:
        return None
    # cachegrind names the per-access counters `D1 misses` / `LLd misses`; the annotated breakdown
    # (read+write) is in the summary lines `D1 misses:  a (b rd + c wr)`.
    rw = re.search(r'D1\s+misses:\s*[\d,]+\s*\(\s*([\d,]+) rd\s*\+\s*([\d,]+) wr\)', txt)
    lrw = re.search(r'LLd misses:\s*[\d,]+\s*\(\s*([\d,]+) rd\s*\+\s*([\d,]+) wr\)', txt)
    return dict(instructions=got.get('I refs'), d_refs=got.get('D refs'),
                d1_misses=got.get('D1 misses', 0),
                d1_read=int(rw.group(1).replace(',', '')) if rw else None,
                d1_write=int(rw.group(2).replace(',', '')) if rw else None,
                ll_misses=got.get('LLd misses', 0),
                ll_read=int(lrw.group(1).replace(',', '')) if lrw else None,
                ll_write=int(lrw.group(2).replace(',', '')) if lrw else None)


def annotate(cgfile, csource, dest):
    """Per-function and per-line rows from cg_annotate, with the event names kept."""
    env = dict(os.environ)
    p = subprocess.run(['cg_annotate', '--show=' + CG_SHOW, '--auto=yes', '--show-percs=no',
                        '--threshold=0.1', str(cgfile)], capture_output=True, text=True, env=env)
    dest.write_text(p.stdout)
    return p.stdout


def per_function(text):
    """[(name, {Ir, Dr, Dw, D1mr, D1mw, DLmr, DLmw})] from a cg_annotate --auto=yes output."""
    rows, in_funcs = [], False
    for line in text.splitlines():
        if line.startswith('-- File:function summary'):
            in_funcs = True
            continue
        if not in_funcs:
            continue
        if line.startswith('-- ') or not line.strip():
            if rows and line.startswith('--'):
                break
            continue
        m = re.match(r'^([<>= ]?)\s*([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(.*)$', line)
        if not m:
            continue
        name = m.group(9).strip()
        if not name or name.startswith('file:function'):
            continue
        rows.append((name, dict(Ir=int(m.group(2).replace(',', '')),
                                Dr=int(m.group(3).replace(',', '')),
                                Dw=int(m.group(4).replace(',', '')),
                                D1mr=int(m.group(5).replace(',', '')),
                                D1mw=int(m.group(6).replace(',', '')),
                                DLmr=int(m.group(7).replace(',', '')),
                                DLmw=int(m.group(8).replace(',', '')))))
    return rows


def func_ranges(path):
    """[(first, last, name)] for the functions defined in `path`, brace counted (as lab/emit does)."""
    src = path.read_text(errors='replace').splitlines()
    out, i = [], 0
    FUNC = re.compile(r'^([A-Za-z_][\w \t\*]*?)\b([A-Za-z_]\w*)\s*\(([^;{]*)\)\s*\{')
    while i < len(src):
        raw = src[i]
        joined = re.sub(r'__attribute__\s*\(\([^;{)]*\)\)\s*', '', raw) if '__attribute__' in raw else raw
        if re.search(r'\bstatic inline\s*$', joined) and '{' not in joined and ';' not in joined:
            if i + 1 < len(src):
                joined = 'static inline ' + src[i + 1]
        m = FUNC.match(joined)
        if m and not joined.lstrip().startswith(('if', 'for', 'while', 'switch', 'return')) \
                and m.group(2) not in ('attribute', 'inline', 'static'):
            depth, j, started = 0, i, False
            while j < len(src):
                s = src[j]
                s = re.sub(r'"(\\.|[^"\\])*"', '""', s)
                s = re.sub(r"'(\\.|[^'\\])*'", "''", s)
                s = s.split('//')[0]
                depth += s.count('{') - s.count('}')
                started = started or '{' in s
                if started and depth <= 0:
                    break
                j += 1
            out.append((i + 1, j + 1, m.group(2)))
            i = j + 1
        else:
            i += 1
    return out


def per_class(text, csource):
    """Charge each annotated source line to the user struct field or runtime container it names.

    The emitted C keeps a struct's columns in `f_<python field>` fields (`v_t->f_par`) and every
    container access goes through a named runtime helper, so the line text is enough to say which
    data structure the traffic belongs to. A line naming both a field and a helper is charged to
    the field (the layout is what this lab is about); a line in neither is charged to the emitted
    function that contains it.
    """
    lines = csource.read_text(errors='replace').splitlines()
    ranges = func_ranges(csource)

    def fn_of(lineno):
        for first, last, name in ranges:
            if first <= lineno <= last:
                return name
        return '?'
    totals = {}

    def add(key, ev):
        t = totals.setdefault(key, dict(Ir=0, Dr=0, Dw=0, D1mr=0, D1mw=0, DLmr=0, DLmw=0))
        for k, v in ev.items():
            t[k] += v

    # cg_annotate --show-percs=no prints seven count columns (a number, or '.' for zero) and then
    # the source text. `-- line N ---` marks the first line of a run; each row after it advances.
    # Only the section for the file we care about is counted: the program also annotates the libc
    # headers it includes, and after them the "Annotation summary" rows would match the same shape.
    cur = 0
    in_src = False
    cols_re = re.compile(r'^\s*([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s(.*)$')
    for line in text.splitlines():
        m = re.match(r'^-- Annotated source file: (.*)$', line)
        if m:
            # The .cg records the path the source was built from; a re-analysis from a different
            # temp directory still has the same basename, so fall back to that.
            in_src = (os.path.realpath(m.group(1)) == os.path.realpath(csource)
                      or os.path.basename(m.group(1)) == os.path.basename(csource))
            cur = 0
            continue
        if line.startswith('-- ') and not line.startswith('-- line '):
            in_src = False          # the next section header re-enables it if it is our file
            continue
        if not in_src:
            continue
        m = re.match(r'^-- line (\d+) -+$', line)
        if m:
            cur = int(m.group(1))
            continue
        m = cols_re.match(line)
        if not m or not cur or cur > len(lines):
            continue
        nums = [0 if g.strip() == '.' else int(g.replace(',', '')) for g in m.groups()[:7]]
        src_text = m.group(8)
        # cg_annotate emits a row per annotated source line in order, so the counter is normally
        # right; realign only when the text disagrees (a line it skipped leaves a row behind).
        if cur <= len(lines) and lines[cur - 1].strip() != src_text.strip():
            moved = _align(lines, cur, src_text)
            if moved:
                cur = moved
        if cur > len(lines):
            continue
        src = lines[cur - 1]
        lineno = cur
        cur += 1
        if not any(nums[:2]):
            continue
        ev = dict(zip(['Ir', 'Dr', 'Dw', 'D1mr', 'D1mw', 'DLmr', 'DLmw'], nums))
        f = FIELD.search(src)
        if f:
            key = 'field:' + f.group(1)
        else:
            name = next((n for n, rx in RUNTIME if rx.search(src)), None)
            key = 'runtime:' + name if name else 'code:' + fn_of(lineno)
        add(key, ev)
    return totals


def _align(lines, cur, text):
    """1-based line at or after `cur` whose stripped text is `text` (whitespace-insensitive)."""
    want = text.strip()
    if not want:
        return cur
    for i in range(max(cur - 1, 0), min(len(lines), cur - 1 + 400)):
        if lines[i].strip() == want:
            return i + 1
    # duplicate/blank text: fall back to a prefix match, then give up and keep the counter
    for i in range(max(cur - 1, 0), min(len(lines), cur - 1 + 400)):
        if lines[i].strip().startswith(want[:40]):
            return i + 1
    return cur


def _fn_at(text, line):
    return 'other'


def wall(binary, c, runs):
    times, rss = [], []
    tfile = binary.parent / (binary.name + '.time')
    for _ in range(runs):
        cmd = [str(binary)] + c['args']
        t0 = time.perf_counter()
        stdin = open(c['path'], 'rb') if c['stdin'] else subprocess.DEVNULL
        try:
            p = subprocess.run(['/usr/bin/time', '-v', '-o', str(tfile), '--'] + cmd, stdin=stdin,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
        finally:
            if c['stdin']:
                stdin.close()
        times.append(time.perf_counter() - t0)
        try:
            m = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', tfile.read_text(errors='replace'))
            if m:
                rss.append(int(m.group(1)))
        except OSError:
            pass
    return dict(best_s=round(min(times), 4), median_s=round(statistics.median(times), 4),
                runs_s=[round(t, 4) for t in times], rc=p.returncode,
                rss_kib=statistics.median(rss) if rss else None)


def one(task, work, runs, want_variants):
    c = case(task, work)
    ref_rc, ref_out = reference(task, c, work)
    csrc = emit(task, work)
    builds = [('ail', csrc, AIL_CFLAGS)]
    cexe = gcc(SRC / task / 'main.c', work / (task + '_c'), C_CFLAGS)
    if want_variants and EDITS.is_dir():
        for script in sorted(EDITS.glob(task + '_*.py')):
            vd = work / (task + '_' + script.stem)
            vd.mkdir(parents=True, exist_ok=True)
            out = vd / 'program.c'
            r = subprocess.run([sys.executable, str(script), str(csrc), str(out)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit('%s: edit failed\n%s%s' % (script, r.stdout, r.stderr))
            builds.append((script.stem[len(task) + 1:], out, AIL_CFLAGS))
    row = dict(task=task, input_bytes=c['bytes'], case=c['name'], builds={})
    cgfiles = {}
    for label, src, flags in builds:
        exe = gcc(src, work / ('%s_%s' % (task, label)), flags)
        p = invoke(exe, c)
        ok = (p.returncode, p.stdout) == (ref_rc, ref_out)
        cg = CG / ('%s_%s.cg' % (task, label))
        counts = run_cg(exe, c, cg)
        text = annotate(cg, src, ANNOT / ('%s_%s.txt' % (task, label))) if counts else ''
        row['builds'][label] = dict(
            ok=ok, bytes=exe.stat().st_size, counts=counts,
            wall=wall(exe, c, runs),
            functions=per_function(text) if text else [],
            classes=per_class(text, src) if text else {})
        print('%s %s instr=%s lld=%s d1=%s ok=%s' % (
            task, label, (counts or {}).get('instructions'), (counts or {}).get('ll_misses'),
            (counts or {}).get('d1_misses'), ok), flush=True)
    cg = CG / (task + '_c.cg')
    counts = run_cg(cexe, c, cg)
    text = annotate(cg, SRC / task / 'main.c', ANNOT / (task + '_c.txt')) if counts else ''
    row['builds']['c'] = dict(ok=True, bytes=cexe.stat().st_size, counts=counts,
                             wall=wall(cexe, c, runs),
                             functions=per_function(text) if text else [],
                             classes=per_class(text, SRC / task / 'main.c') if text else {})
    print('%s c instr=%s lld=%s d1=%s' % (task, (counts or {}).get('instructions'),
                                          (counts or {}).get('ll_misses'),
                                          (counts or {}).get('d1_misses')), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--out', default=str(DATA))
    ap.add_argument('--variants', action='store_true')
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    CG.mkdir(parents=True, exist_ok=True)
    ANNOT.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in args.tasks.split(',') if t]
    if not shutil.which('valgrind'):
        raise SystemExit('valgrind not on PATH (see lab/energy/run.sh ensure_valgrind)')
    out = Path(args.out) / 'layout.json'
    rows = json.loads(out.read_text()) if out.is_file() else {}
    with tempfile.TemporaryDirectory(prefix='layout-') as tmp:
        work = Path(tmp)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(one, t, work, args.runs, args.variants): t for t in tasks}
            for fut, t in futs.items():
                try:
                    rows[t] = fut.result()
                except Exception as e:
                    rows[t] = dict(task=t, error='%s: %s' % (type(e).__name__, e))
                    print(t, 'ERROR', rows[t]['error'], flush=True)
                out.write_text(json.dumps(rows, indent=1) + '\n')
    out.write_text(json.dumps(rows, indent=1) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main()
