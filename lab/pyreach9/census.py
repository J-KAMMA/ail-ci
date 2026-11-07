#!/usr/bin/env python3
"""Typed-reach census for pyreach9.

    python3 lab/pyreach9/census.py [-j 2] [--timeout 300] [-o lab/pyreach9/census.jsonl]

Corpora (fixed order):
  compare  the ten lab/compare/src/*/main.py, with the task flags run_task.py uses
           (--exact-int for chain_relax and rail_transfer)
  vibe     every *.py under lab/vibe/programs (the Python the AI wrote for both the
           python and ail columns; ail-0.py is plain Python too)
  gdev     100 of corpus/gdev/*.py, drawn with random.Random(20261107).sample from the
           sorted file list

For each program we record:
  path      typed when `compile --syntax python --strict` succeeds; otherwise general
            when the default build succeeds; otherwise refused
  blockers  every blocker the compiler's strict collector found (`--strict --json`),
            not only the first: construct, why, line, function, statement, rank
  default   the general-path note or the first refusal of the default build

The compiler is not modified.  Each build runs in its own temp directory with
AIL_NO_CACHE=1.  At most --jobs programs are in flight.
"""
import argparse
import concurrent.futures
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
SEED = 20261107
EXACT_INT = {'chain_relax', 'rail_transfer'}


def _rel(path):
    return str(Path(path).relative_to(ROOT))


def corpora():
    compare = sorted(ROOT.glob('lab/compare/src/*/main.py'))
    vibe = sorted(ROOT.glob('lab/vibe/programs/*/*.py'))
    gdev_all = sorted(ROOT.glob('corpus/gdev/*.py'))
    gdev = sorted(random.Random(SEED).sample(gdev_all, 100))
    return [('compare', p) for p in compare] + [('vibe', p) for p in vibe] + \
        [('gdev', p) for p in gdev]


def flags_for(path):
    name = path.parent.name
    return ['--exact-int'] if name in EXACT_INT and path.parent.parent.name == 'src' else []


def _run(cmd, cwd, timeout):
    env = dict(os.environ, AIL_NO_CACHE='1')
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout,
                           env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout after %s s' % timeout


def _first_reason(text):
    for line in (text or '').splitlines():
        line = line.strip()
        if line:
            return line
    return ''


def census_one(item, timeout):
    corpus, path = item
    rec = {'corpus': corpus, 'name': _rel(path),
           'bytes': path.stat().st_size, 'lines': path.read_text(errors='replace').count('\n') + 1}
    work = Path(tempfile.mkdtemp(prefix='pyreach9-'))
    flags = flags_for(path)
    rec['flags'] = flags
    try:
        base = [sys.executable, '-B', str(AIL), 'compile', str(path), '--syntax', 'python'] + flags
        # strict first: a typed strict build settles the path without a general attempt
        start = time.monotonic()
        rc, out, err = _run(base + ['--strict', '--json', '-o', str(work / 'strict.out')], ROOT, timeout)
        rec['strict_seconds'] = round(time.monotonic() - start, 2)
        rec['strict_exit'] = rc
        blockers, incomplete = [], None
        if rc == 0:
            rec['path'] = 'typed'
        else:
            try:
                doc = json.loads(out)
            except Exception:
                doc = None
            if isinstance(doc, dict) and doc.get('schema') == 'ail.strict/1':
                incomplete = doc.get('incomplete')
                for b in doc.get('blockers', []):
                    blockers.append({k: b.get(k) for k in (
                        'rank', 'line', 'column', 'function', 'statement', 'construct', 'why',
                        'write_instead', 'blocks_lines', 'blocks_functions', 'message')})
            rec['strict_blockers'] = blockers
            rec['strict_incomplete'] = incomplete
            rec['strict_first'] = _first_reason(err) or (
                blockers[0].get('message') if blockers else '')
            # default build: general path or refused
            start = time.monotonic()
            rc2, out2, err2 = _run(base + ['-o', str(work / 'default.out')], ROOT, timeout)
            rec['default_seconds'] = round(time.monotonic() - start, 2)
            rec['default_exit'] = rc2
            note = ''
            for line in (err2 or '').splitlines():
                if 'built on the general path' in line:
                    note = line.strip()
                    break
            rec['default_note'] = note
            if rc2 == 0:
                rec['path'] = 'general'
            else:
                rec['path'] = 'refused'
                rec['default_first'] = _first_reason(err2)
        return rec
    except Exception as e:
        rec['path'] = 'error'
        rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('-o', '--out', default=str(Path(__file__).resolve().parent / 'census.jsonl'))
    args = ap.parse_args()
    items = corpora()
    print('programs:', len(items), {c: sum(1 for k, _ in items if k == c)
                                    for c in ('compare', 'vibe', 'gdev')}, flush=True)
    results = {}
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futures = {ex.submit(census_one, item, args.timeout): item for item in items}
        for f in concurrent.futures.as_completed(futures):
            corpus, path = futures[f]
            rec = f.result()
            results[(corpus, path)] = rec
            print('%-8s %-58s %-8s strict %s default %s %5.1fs' % (
                corpus, _rel(path), rec.get('path'), rec.get('strict_exit', '-'),
                rec.get('default_exit', '-'), rec.get('strict_seconds', 0) + rec.get('default_seconds', 0)),
                flush=True)
    out = Path(args.out)
    with out.open('w') as fh:
        for item in items:
            fh.write(json.dumps(results[item], sort_keys=True) + '\n')
    counts = {}
    for rec in results.values():
        counts[rec.get('path')] = counts.get(rec.get('path'), 0) + 1
    print('wrote %s in %.1fs: %s' % (out, time.monotonic() - start, counts))


if __name__ == '__main__':
    main()
