#!/usr/bin/env python3
"""Byte identity of the generated C, the executable and the refusal text (ctpred1, Appendix B).

Builds the 10 ``typed.py``, the 10 ``main.py``, the first 200 sorted
``lab/corpus/programs/*/*.py`` and ``docs/design/alias_study/trans`` (when present) with
``--debug-dir``, ``PYTHONHASHSEED=0``, ``AIL_NO_CACHE=1``, ``AIL_SERVER=0`` and a fresh
``AIL_CACHE``, then stores ``sha256(program.c)``, ``sha256(executable)`` and the
``sha256`` of the refusal text.  A program the compiler refuses has no C or executable, only a
refusal hash.

    python3 lab/profile/ccheck.py --base          # record the hashes in CTIME_PRED.json
    python3 lab/profile/ccheck.py --check         # compare against them, exit 1 on a mismatch

Two builds run at a time (the repo's ``-j 2`` cap); every build is wrapped in
``RLIMIT_AS = 1500000`` KiB.  The work directory, the output and the compiler's own
``ailc-XXXXXX`` temp directory are replaced with placeholders in a refusal text, so the hash is a
hash of the message, not of the temp names.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
CORPUS = REPO / 'lab' / 'corpus' / 'programs'
ALIAS = REPO / 'docs' / 'design' / 'alias_study' / 'trans'
RECORD = HERE / 'CTIME_PRED.json'
LIMIT = 1500000
WORKERS = 2


def inputs():
    rows = []
    for task in sorted(path.parent.name for path in SRC.glob('*/main.ail')):
        for name in ('typed.py', 'main.py'):
            path = SRC / task / name
            if path.is_file():
                rows.append((task + '/' + name, path))
    for path in sorted(CORPUS.glob('*/*.py'))[:200]:
        rows.append((str(path.relative_to(REPO)), path))
    if ALIAS.is_dir():
        for path in sorted(ALIAS.glob('*.py')):
            rows.append((str(path.relative_to(REPO)), path))
    elif ALIAS.is_file():
        rows.append((str(ALIAS.relative_to(REPO)), ALIAS))
    return rows


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT * 1024, LIMIT * 1024))


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha(text):
    return hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()


def build_one(name, source):
    work = Path(tempfile.mkdtemp(prefix='ailccheck-'))
    try:
        for sub in ('cache', 'tmp'):
            (work / sub).mkdir(parents=True, exist_ok=True)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith('AIL_') and key not in ('PIPE_CC', 'PYTHONPATH')}
        env.update(PYTHONUTF8='1', PYTHONHASHSEED='0', AIL_SERVER='0', AIL_NO_CACHE='1',
                   AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'))
        target = work / 'prog'
        debug = work / 'debug'
        command = [sys.executable, '-X', 'utf8', '-B', str(AIL), 'compile', str(source),
                   '-o', str(target), '--debug-dir', str(debug), '--syntax', 'python']
        done = subprocess.run(command, cwd=str(work), env=env, capture_output=True, text=True,
                              timeout=1800, preexec_fn=limit_memory)
        row = {'source': str(source), 'returncode': done.returncode}
        c_path = debug / 'program.c'
        if c_path.is_file():
            row['c'] = _sha(c_path)
        if target.is_file():
            row['exe'] = _sha(target)
        if done.returncode != 0:
            text = (done.stdout + done.stderr)
            for prefix in (str(work), str(target), str(source)):
                text = text.replace(prefix, '<path>')
            # The compiler writes program.c into a fresh `ailc-XXXXXX` under TMPDIR, so the
            # gcc message carries a random component that is not part of the refusal.
            text = re.sub(r'ailc-[A-Za-z0-9_]+', 'ailc-<tmp>', text)
            row['refusal'] = _text_sha(text)
            lines = [line.strip() for line in done.stderr.splitlines() if line.strip()]
            row['reason'] = lines[-1][:300] if lines else ''
        return name, row
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run(rows):
    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for name, row in pool.map(lambda item: build_one(*item), rows):
            results[name] = row
    return results


def load_record():
    if RECORD.is_file():
        try:
            return json.loads(RECORD.read_text(encoding='utf8'))
        except ValueError:
            return {}
    return {}


def save_record(record):
    RECORD.write_text(json.dumps(record, indent=1, sort_keys=True) + '\n', encoding='utf8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--base', action='store_true', help='record the hashes')
    group.add_argument('--check', action='store_true', help='compare against the record')
    args = parser.parse_args(argv)
    rows = inputs()
    print('inputs: %d (alias_study/trans %s)' % (len(rows), 'present' if ALIAS.exists() else 'absent'),
          flush=True)
    results = run(rows)
    record = load_record()
    if args.base:
        record['byte_identity'] = {'inputs': results, 'count': len(results),
                                   'alias_study_trans': ALIAS.exists()}
        save_record(record)
        refusals = sum(1 for row in results.values() if 'refusal' in row)
        print('recorded %d inputs (%d refused, %d built) in %s'
              % (len(results), refusals, len(results) - refusals, RECORD))
        return 0
    base = (record.get('byte_identity') or {}).get('inputs') or {}
    mismatches = []
    for name, row in results.items():
        old = base.get(name)
        if old is None:
            mismatches.append((name, 'missing'))
            continue
        for key in ('c', 'exe', 'refusal', 'returncode'):
            if row.get(key) != old.get(key):
                mismatches.append((name, key))
    if not base:
        print('no recorded hashes; run --base first')
        return 2
    if mismatches:
        for name, key in mismatches:
            print('MISMATCH %s %s' % (name, key))
        print('%d mismatch(es)' % len(mismatches))
        return 1
    print('all %d inputs identical' % len(results))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
