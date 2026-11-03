#!/usr/bin/env python3
"""Build each program twice with AIL_FE_CACHE=1 and compare the C the compiler saw.

The first build fills a fresh cache; the second must be a hit and must hand the compiler
byte-identical C.  Covers lab/compare/src and the lab/corpus programs.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
WRAPPER = HERE / 'cc_wrap.py'
COMPARE = REPO / 'lab' / 'compare' / 'src'
CORPUS = REPO / 'lab' / 'corpus' / 'programs'


def files_hash(directory):
    h = hashlib.sha256()
    for data in sorted(path.read_bytes() for path in pathlib.Path(directory).glob('*')):
        h.update(len(data).to_bytes(8, 'little') + data)
    return h.hexdigest()


def env_for(work):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key != 'PIPE_CC'}
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', AIL_SERVER='0',
               AIL_NO_CACHE='1', AIL_FE_CACHE='1',
               AIL_FE_CACHE_DIR=str(work / 'fe'), AIL_FE_CACHE_LOG=str(work / 'fe.log'),
               PIPE_CC=str(WRAPPER), WRAP_CC=shutil.which('gcc') or 'gcc',
               WRAP_MODE='single', WRAP_LOG=str(work / 'cc.jsonl'))
    return env


def build(source, out, saved, work, env, syntax):
    saved.mkdir(parents=True)
    run_env = dict(env, WRAP_SAVE_C=str(saved))
    command = [sys.executable, '-X', 'utf8', '-B', str(AIL), 'compile']
    if syntax:
        command += ['--syntax', syntax]
    command += [str(source), '-o', str(out)]
    done = subprocess.run(command, cwd=str(work), env=run_env, capture_output=True,
                          text=True, timeout=300)
    return done


def check(source, syntax, work):
    work.mkdir(parents=True)
    env = env_for(work)
    first = build(source, work / 'one', work / 'c1', work, env, syntax)
    second = build(source, work / 'two', work / 'c2', work, env, syntax)
    events = (work / 'fe.log').read_text().splitlines() if (work / 'fe.log').exists() else []
    result = {'source': str(source), 'syntax': syntax, 'ok': False,
              'first_rc': first.returncode, 'second_rc': second.returncode,
              'events': events}
    if first.returncode or second.returncode:
        result['stderr'] = (first.stderr or second.stderr)[-1000:]
        return result
    result['c1'] = files_hash(work / 'c1')
    result['c2'] = files_hash(work / 'c2')
    result['identical'] = result['c1'] == result['c2']
    result['hit'] = bool(events) and events[-1].startswith('hit ')
    result['ok'] = result['identical'] and result['hit']
    if not result['identical']:
        result['c1_files'] = sorted(path.name for path in (work / 'c1').glob('*'))
        result['c2_files'] = sorted(path.name for path in (work / 'c2').glob('*'))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--out', default=str(HERE / 'verify.json'))
    args = parser.parse_args()
    cases = [(path, 'python') for path in sorted(COMPARE.glob('*/typed.py'))]
    if args.corpus:
        corpus = sorted(CORPUS.glob('*/*.py'))
        if args.limit:
            corpus = corpus[:args.limit]
        cases.extend((path, 'python') for path in corpus)
    root = pathlib.Path(tempfile.mkdtemp(prefix='ail-fe-verify-'))
    started = time.time()
    results = []

    def one(index_case):
        index, (source, syntax) = index_case
        work = root / ('%04d' % index)
        try:
            return check(source, syntax, work)
        except Exception as error:
            return {'source': str(source), 'syntax': syntax, 'ok': False,
                    'error': '%s: %s' % (type(error).__name__, error)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(one, enumerate(cases)):
            results.append(result)
            if not result['ok']:
                print('FAIL', result['source'], result.get('error') or result.get('stderr', '')[-300:],
                      file=sys.stderr, flush=True)
    summary = {'total': len(results), 'ok': sum(result['ok'] for result in results),
               'failed': [result for result in results if not result['ok']],
               'elapsed_s': round(time.time() - started, 1), 'work': str(root)}
    pathlib.Path(args.out).write_text(json.dumps({'summary': summary, 'results': results}, indent=1) + '\n',
                                      encoding='utf-8')
    print('verified %d/%d in %.1fs; wrote %s' % (summary['ok'], summary['total'],
                                                summary['elapsed_s'], args.out), file=sys.stderr)
    return 0 if summary['ok'] == summary['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
