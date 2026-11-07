#!/usr/bin/env python3
"""Check a hand-edited copy of the emitted C against CPython on boundary inputs.

    python3 lab/layout/probe.py tree_fold flat

The perf input every table in RESULTS.md uses is one case; this runs the task's own public and
hidden cases (its `gen.py`) plus a few synthetic boundaries (empty, one element, all-equal keys,
maximum-width values) through the CPython source and the hand-edited C, and requires byte-identical
stdout and exit code. A variant that only matched the perf input would be a special case, not a
layout change.
"""
import importlib.util
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / 'lab' / 'compare' / 'src'
GEN = REPO / 'lab' / 'compare' / 'tasks'
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
AIL_CFLAGS = ['-O2', '-g', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd']


def build(task, label, work):
    dbg = work / (task + '.d')
    exe = work / (task + '_' + label)
    p = subprocess.run([sys.executable, '-B', str(AIL), 'compile', str(SRC / task / 'typed.py'),
                        '--syntax', 'python', '-o', str(work / task), '--debug-dir', str(dbg)],
                       capture_output=True, timeout=1800)
    if p.returncode:
        raise SystemExit('AIL compile failed: ' + p.stderr.decode()[-2000:])
    csrc = dbg / 'program.c'
    if label != 'ail':
        script = HERE / 'edits' / ('%s_%s.py' % (task, label))
        edited = work / ('program_%s.c' % label)
        r = subprocess.run([sys.executable, str(script), str(csrc), str(edited)],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('edit failed: ' + r.stdout + r.stderr)
        csrc = edited
    r = subprocess.run(['gcc'] + AIL_CFLAGS + ['-o', str(exe), str(csrc), '-lm'],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('gcc failed: ' + r.stderr[-2000:])
    return exe


def cases(task, work):
    spec = importlib.util.spec_from_file_location('g' + task, GEN / task / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    public, hidden, perf = m.cases(random.Random('%s-20261012' % task))
    out = [('perf', perf)] + [('public/%s' % c[0], c) for c in public] + \
          [('hidden/%s' % c[0], c) for c in hidden]
    extra = EXTRA.get(task, [])
    for name, data in extra:
        out.append(('boundary/%s' % name, (name, data, [])))
    made = []
    for k, (name, (case, data, args)) in enumerate(out):
        path = work / ('%s-%d.bin' % (task, k))
        path.write_bytes(data)
        made.append((name, path, [a.replace('{input}', str(path)) for a in args],
                     bool(getattr(m, 'STDIN', False))))
    return made


def run(cmd, path, args, stdin):
    fh = open(path, 'rb') if stdin else subprocess.DEVNULL
    try:
        p = subprocess.run(cmd + args, stdin=fh, capture_output=True, timeout=1200)
        return p.returncode, p.stdout
    finally:
        if stdin:
            fh.close()


# Synthetic boundaries. These are task-shaped inputs at the edges of the layout decisions, not
# extra test cases for the task: empty, one item, all-equal keys, and maximum-width lengths.
EXTRA = {
    'tree_fold': [('empty', b''),
                  ('one-node', b'a:1\n'),
                  ('one-node-ops', b'a:1\ntotal\nstats\nprint\n'),
                  ('deep-chain', b'a:1[' + b'b:1[' * 40 + b'c:1' + b']' * 41 + b'\n'),
                  ('all-equal-sub', (b'a:1[' + b'b:1[' * 20 + b'c:1' + b']' * 21 + b'\nsort\nmirror\nfold\nstats\n')),
                  ('max-weight', b'a:1000000\nb:1000000\ntotal\n'),
                  ('sort-single', b'a:1[b:2]\nsort\nprint\n'),
                  ('sort-none', b'a:1[b:2 c:3]\nsort\nmirror\nstats\n')],
    'berth_sim': [('zero-ships', b'1 0\n1 1\n'),
                  ('one-ship', b'1 1\n1 1\n1 0 1 5 1 0\n'),
                  ('two-ships-same-arrival', b'1 2\n1 1\n1 0 1 5 1 0\n2 0 1 5 1 0\n'),
                  ('all-same-keys', b'1 3\n1 1\n1 0 1 5 1 0\n1 0 2 5 1 0\n1 0 1 5 1 0\n')],
    'echo_pack': [('empty', b''),
                  ('one-byte', b'a'),
                  ('three-bytes', b'abc'),
                  ('four-same', b'aaaa'),
                  ('repeat', b'abcdabcdabcdabcd'),
                  ('zeros', b'\x00' * 16)],
    'ledger_bin': [('empty', b''),
                   ('short', b'\xc7LXF\x02\x00'),
                   ('header-only', b'\xc7LXF\x02\x00')],
    'ticket_audit': [('empty', b''),
                     ('header-only', b'TKT/1\n')],
}


def main():
    task = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else 'ail'
    rc = 0
    with tempfile.TemporaryDirectory(prefix='probe-') as tmp:
        work = Path(tmp)
        exe = build(task, label, work)
        ref = SRC / task / 'main.py'
        for name, path, args, stdin in cases(task, work):
            py = run([sys.executable, str(ref)], path, args, stdin)
            got = run([str(exe)], path, args, stdin)
            ok = py == got
            rc |= 0 if ok else 1
            print('%-14s %-28s %s' % (task, name, 'same' if ok else 'DIFF'))
            if not ok:
                print('   cpython rc=%d bytes=%d  variant rc=%d bytes=%d' % (
                    py[0], len(py[1]), got[0], len(got[1])))
    return rc


if __name__ == '__main__':
    sys.exit(main())
