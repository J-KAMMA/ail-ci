#!/usr/bin/env python3
"""Measure AIL-emitted C against the hand-written C baseline with callgrind.

This is the measurement behind lab/emit/RESULTS.md.  It builds each task from
lab/compare/src, runs the same perf input through both binaries under
callgrind (Ir only), checks stdout is identical, and records the program total,
the AIL/C ratio and the ten hottest emitted functions.

    python3 lab/emit/analyze.py                 # all six, writes data/measured.json
    python3 lab/emit/analyze.py --tasks echo_pack
    python3 lab/emit/analyze.py --out /tmp/m.json

valgrind must be on PATH (and VALGRIND_LIB set if it is an unpacked package).
The numbers in RESULTS.md were produced with valgrind 3.22.0.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOF = REPO / 'lab' / 'roof'
SRC = REPO / 'lab' / 'compare' / 'src'
TASKS = ['ticket_audit', 'echo_pack', 'tree_fold', 'ledger_bin', 'tally_lang', 'berth_sim']
AIL_CFLAGS = ['-O2', '-g', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd']
C_CFLAGS = ['-O2', '-g', '-std=c11']

spec = importlib.util.spec_from_file_location('roof_attrib', ROOF / 'attrib.py')
attrib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attrib)

FUNC = re.compile(r'^([A-Za-z_][\w \t\*]*?)\b([A-Za-z_]\w*)\s*\(([^;{]*)\)\s*\{')
SOURCE = re.compile(r'^-- (?:Auto|User)-annotated source: (.*)$')
LINE = re.compile(r'^-- line (\d+) ---')
IR_LINE = re.compile(r'^\s*([\d,]+)\s+\(\s*[\d.]+%\)\s+(.*)$')
DOT_LINE = re.compile(r'^\s*\.\s+(.*)$')
TOTAL = re.compile(r'([\d,]+) \(100.0%\)  PROGRAM TOTALS')
SUMMARY = re.compile(r'^\s*([\d,]+)\s+\([^)]*\)\s+(.*?)\s+\[(.*)\]$')


def build(task, work):
    dbg = work / (task + '.d')
    if dbg.exists():
        shutil.rmtree(dbg)
    exe = work / (task + '_ail_g')
    cmd = [sys.executable, '-B', str(REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'), 'compile',
           str(SRC / task / 'typed.py'), '--syntax', 'python', '-o', str(work / (task + '_ail')),
           '--debug-dir', str(dbg)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if p.returncode:
        raise SystemExit('%s: AIL compile failed\n%s' % (task, p.stderr[-3000:]))
    csrc = dbg / 'program.c'
    r = subprocess.run(['gcc'] + AIL_CFLAGS + ['-o', str(exe), str(csrc), '-lm'],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('%s: gcc (AIL) failed\n%s' % (task, r.stderr[-3000:]))
    cexe = work / (task + '_c_g')
    r = subprocess.run(['gcc'] + C_CFLAGS + ['-o', str(cexe), str(SRC / task / 'main.c'), '-lm'],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('%s: gcc (C) failed\n%s' % (task, r.stderr[-3000:]))
    return csrc, exe, cexe


def func_ranges(path):
    """[(first, last, name)] for the functions defined in `path`, brace counted.

    Emitted helpers are written as `static __attribute__((noinline, cold)) void f(...) {`
    and a few as `__attribute__((always_inline)) static inline` on a line of their own, so
    strip the attribute decorator and join that two-line form before matching; otherwise the
    name comes out as `__attribute__` and every macro/attribute helper is mislabelled.
    """
    lines = path.read_text(errors='replace').splitlines()
    out, i = [], 0
    while i < len(lines):
        raw = lines[i]
        joined = re.sub(r'__attribute__\s*\(\([^;{)]*\)\)\s*', '', raw) if '__attribute__' in raw else raw
        if re.search(r'\bstatic inline\s*$', joined) and '{' not in joined and ';' not in joined:
            if i + 1 < len(lines):
                joined = 'static inline ' + lines[i + 1]
        m = FUNC.match(joined)
        if m and not joined.lstrip().startswith(('if', 'for', 'while', 'switch', 'return')) \
                and m.group(2) not in ('attribute', 'inline', 'static'):
            depth, j, started = 0, i, False
            while j < len(lines):
                s = lines[j]
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


def func_at(ranges, line):
    for first, last, name in ranges:
        if first <= line <= last:
            return name
    return '?'


def _align(src, cur, text):
    """1-based line in `src` whose stripped text is `text`, at or after `cur`.

    `-- line N ---` markers and the source file are the authority.  A marker is
    trusted; the text lookup only repairs a gap (a source line callgrind omitted),
    with a bounded forward search so a wrong guess cannot run away.
    """
    if src is None:
        return cur
    t = text.strip()
    i = cur - 1
    if 0 <= i < len(src) and src[i].strip() == t:
        return cur
    for j in range(max(0, i), min(len(src), i + 200)):
        if src[j].strip() == t:
            return j + 1
    return cur


def parse_annotate(path, want, source_path=None):
    """Rows of source-line Ir from the one auto-annotated source ending in `want`.

    callgrind_annotate inserts `-- line N ---` jumps; without following them every
    row after the first jump is attributed to the wrong source line.  `=>` rows are
    the callee's inclusive cost, already counted in the callee, so they are skipped
    *and* do not advance the source line -- they occupy no line of their own, and
    advancing on them shifted every later row.  When the source file is available,
    each row is also aligned to the text of that line, so an omitted row cannot
    silently shift the rest.
    """
    src = None
    if source_path is not None:
        try:
            src = Path(source_path).read_text(errors='replace').splitlines()
        except OSError:
            src = None
    rows, cur, source = [], 0, None
    for line in path.read_text(errors='replace').splitlines():
        m = SOURCE.match(line)
        if m:
            # callgrind_annotate prints the source from line 1 unless a `-- line N ---`
            # jump marker says otherwise; starting at 0 dropped every row before the
            # first marker (all of main.c's prefix, which made the C side look free).
            source, cur = m.group(1), 1
            continue
        m = LINE.match(line)
        if m:
            cur = int(m.group(1))
            continue
        if 'events annotated' in line:
            break
        if source is None or not source.endswith(want) or cur == 0:
            continue
        m = IR_LINE.match(line)
        if m:
            text = m.group(2)
            if text.lstrip().startswith('=>'):
                continue
            cur = _align(src, cur, text)
            rows.append((cur, int(m.group(1).replace(',', '')), text))
            cur += 1
            continue
        m = DOT_LINE.match(line)
        if m:
            # a zero-cost source line; advance it too, or the rows after it drift
            if m.group(1).strip():
                cur = _align(src, cur, m.group(1))
            cur += 1
    return rows


def parse_summary(path, csrc):
    """[(Ir, function)] for functions located in the generated `csrc`.

    The table has a separator both above and below it; the first one must be
    skipped, not treated as the end, or every function is dropped (the summary
    then also loses the hottest-function ranking for `measured.json`).
    """
    out, on, seen = [], False, False
    for line in path.read_text(errors='replace').splitlines():
        if 'file:function' in line and line.lstrip().startswith('Ir'):
            on = True
            continue
        if not on:
            continue
        if line.startswith('---'):
            if seen:
                break
            continue
        m = SUMMARY.match(line)
        if not m:
            if seen:
                break
            continue
        seen = True
        loc = m.group(2)
        if (csrc.name + ':') in loc:
            out.append((int(m.group(1).replace(',', '')), loc.split(':', 1)[1]))
    return out


def callgrind(exe, case, cg, env):
    stdin = open(case['path'], 'rb') if case['stdin'] else subprocess.DEVNULL
    try:
        return subprocess.run(['valgrind', '--tool=callgrind', '--cache-sim=no',
                               '--branch-sim=no', '--callgrind-out-file=' + str(cg),
                               str(exe)] + case['args'], stdin=stdin,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, timeout=3600)
    finally:
        if case['stdin']:
            stdin.close()


def measure(task, work, env):
    csrc, exe, cexe = build(task, work)
    case = attrib.case(task, work)
    mains = SRC / task / 'main.c'
    rec = {'src': str(SRC / task / 'typed.py'), 'funcs': func_ranges(csrc),
           'cfuncs': func_ranges(mains)}
    for lang, binary, source in (('ail', exe, csrc), ('c', cexe, mains)):
        cg = work / (task + '_' + lang + '.cg')
        ann = work / (task + '_' + lang + '.ann')
        t0 = time.time()
        p = callgrind(binary, case, cg, env)
        a = subprocess.run(['callgrind_annotate', '--auto=yes', '--threshold=100',
                            '--show=Ir', str(cg)], capture_output=True, text=True, env=env)
        ann.write_text(a.stdout)
        total = int(TOTAL.search(a.stdout).group(1).replace(',', ''))
        rec[lang] = {'total': total, 'sec': round(time.time() - t0, 2),
                     'rows': parse_annotate(ann, source.name, source),
                     'summary': parse_summary(ann, source)}
        (work / (task + '_' + lang + '.out')).write_bytes(p.stdout)
        print('%-13s %-3s %15s Ir  %6.1fs' % (task, lang, format(total, ','), rec[lang]['sec']),
              flush=True)
    rec['stdout_same'] = (work / (task + '_ail.out')).read_bytes() == \
                         (work / (task + '_c.out')).read_bytes()
    if not rec['stdout_same']:
        raise SystemExit('%s: AIL and C stdout differ' % task)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', default=','.join(TASKS))
    ap.add_argument('--work', default='/tmp/ail-emit-measure')
    ap.add_argument('--out', default=str(HERE / 'data' / 'measured.json'))
    ap.add_argument('--lines', default=str(HERE / 'data' / 'lines.json'),
                    help='per-source-line Ir for every task (classify.py reads this)')
    args = ap.parse_args()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if shutil.which('valgrind') is None:
        raise SystemExit('valgrind is not on PATH; put it there or set PATH/VALGRIND_LIB')
    data = {'method': {'ail_cflags': AIL_CFLAGS, 'c_cflags': C_CFLAGS,
                       'tool': 'callgrind Ir only', 'input': 'lab/roof/attrib.py:case()'},
            'tasks': {}}
    lines = {'method': {'fields': 'line, ir, text, fn for every emitted program.c line'},
             'tasks': {}}
    for task in args.tasks.split(','):
        if task not in TASKS:
            raise SystemExit('unknown task %r' % task)
        rec = measure(task, work, env)
        a, c = rec['ail']['total'], rec['c']['total']
        data['tasks'][task] = {
            'ail': a, 'c': c, 'extra': a - c, 'ratio': round(a / c, 3),
            'stdout_same': rec['stdout_same'],
            'top': [[name, ir] for ir, name in rec['ail']['summary'][:10]],
            'top_c': [[name, ir] for ir, name in rec['c']['summary'][:10]],
        }
        lines['tasks'][task] = {
            lang: [{'line': ln, 'ir': ir, 'text': text, 'fn': name}
                   for ln, ir, text, name in (
                       [(r[0], r[1], r[2],
                         func_at(rec['funcs' if lang == 'ail' else 'cfuncs'], r[0]))
                        for r in rec[lang]['rows']])]
            for lang in ('ail', 'c')}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + '\n')
    lout = Path(args.lines)
    lout.parent.mkdir(parents=True, exist_ok=True)
    lout.write_text(json.dumps(lines, indent=0, sort_keys=False) + '\n')
    print('wrote', out, lout)


if __name__ == '__main__':
    main()
