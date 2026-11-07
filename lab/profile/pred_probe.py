#!/usr/bin/env python3
"""How much of the ``pyfunc`` type/kind predicate time is repeated work with an unchanged answer.

Wraps the predicates from outside, in the compiler child process, through a ``sitecustomize``
in a temp directory (the same device ``lab/selfhost/hot_functions.py`` and ``lab/profile/run.py``
use).  ``pyfunc.py`` is never edited.

For each call the wrapper records a key, the own time, and ``repr(result)``:

* the key is ``id()`` of every non-primitive argument (the AST node and the ``Ctx``) plus the
  value of every primitive one, so a cache keyed on the node and the other arguments is
  reproducible from the record; objects are held alive for the whole run so ids are not reused;
* a *repeat* is a call whose key was seen before; a *changed* repeat is one whose result repr
  differs from the first answer for that key, i.e. the predicate reads state that changes during
  the build and a plain memo would be wrong for it;
* *cacheable* seconds are the own time of the repeats whose answer did not change.

Own time is the time inside the predicate body only.  The whole interval of a wrapped callee --
its key construction, its bookkeeping and its own recording included -- is subtracted from the
caller, and a predicate's own recording is excluded from its own time, so the probe's
instrumentation is not charged to any predicate.

    python3 lab/profile/pred_probe.py --tasks berth_sim chain_relax tally_lang --out-dir /tmp/pred
    python3 lab/profile/pred_probe.py --corpus --out-dir /tmp/pred
    python3 lab/profile/pred_probe.py --report /tmp/pred --corpus-dir /tmp/predcorpus \\
        --out-json lab/profile/CTIME_PRED.json
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
CORPUS = REPO / 'lab' / 'corpus' / 'programs'
LIMIT = 1500000

# module-level functions with signature (node, ctx) or (fn, ...), plus the Ctx method
FUNCTIONS = ('_etype', '_is_str_expr', '_is_slist_expr', '_map_kind',
             '_is_bytes_expr', '_is_owned_bytes_call')
METHODS = (('Ctx', 'type_of'),)
EXTRA = ('_param_kinds',)
PREDICATES = FUNCTIONS + tuple(name for _, name in METHODS) + EXTRA

SITECUSTOMIZE = '''\
import os, sys
if any(a.endswith('pyc.py') for a in sys.argv):
    root = os.environ.get('AILPRED_DIR')
    out = os.environ.get('AILPRED_OUT')
    names = os.environ.get('AILPRED_LIST', '')
    mode = os.environ.get('AILPRED_MODE', 'full')
    if root and out:
        script = next((a for a in sys.argv if a.endswith('pyc.py')), None)
        package = os.path.dirname(os.path.abspath(script)) if script else None
        if package and package not in sys.path:
            sys.path.insert(0, package)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            import pred_probe
            pred_probe.install(out, names.split(','), mode)
        except BaseException as error:
            with open(out + '.err', 'w', encoding='utf8') as handle:
                handle.write(repr(error))
'''


def _primitive(value):
    return isinstance(value, (str, bytes, int, float, bool, type(None)))


def install(out_path, names, mode):
    """Called from the child's ``sitecustomize`` before ``pyc.py`` imports ``pyfunc``."""
    import pyfunc

    timing = mode != 'changed'
    state = {name: {'calls': 0, 'own': 0.0, 'cacheable': 0.0, 'changed': 0,
                    'changed_keys': set(), 'raises': 0, 'unhashable': 0, 'keys': {}}
             for name in names}
    alive = []
    clock = time.perf_counter
    stack = []

    def token(value):
        if _primitive(value):
            return value
        alive.append(value)
        return id(value)

    def text_of(result):
        if isinstance(result, (str, int, float, bool, type(None))):
            return result
        return _repr(result)

    def record(name, args, kwargs, seconds, result):
        entry = state[name]
        entry['calls'] += 1
        entry['own'] += seconds
        mark = clock()
        key = (tuple(token(a) for a in args),
               tuple(sorted((k, token(v)) for k, v in kwargs.items())))
        keys = entry['keys']
        first = keys.get(key)
        text = result
        if first is None:
            keys[key] = [text, 0]
        else:
            first[1] += 1
            if text != first[0]:
                entry['changed'] += 1
                entry['changed_keys'].add(key)
            else:
                entry['cacheable'] += seconds
        if stack:
            # Charge the whole recording interval to the caller's child time, so the
            # probe's own bookkeeping is not counted as any predicate's own time.
            stack[-1][1] += clock() - mark

    def finish():
        stop = clock()
        start, children = stack.pop()
        seconds = stop - start - children
        if stack:
            stack[-1][1] += stop - start
        return seconds

    def wrap(name, function):
        def wrapper(*args, **kwargs):
            if timing:
                stack.append([clock(), 0.0])
                try:
                    result = function(*args, **kwargs)
                except BaseException as error:
                    record(name, args, kwargs, finish(), '!raise ' + type(error).__name__)
                    state[name]['raises'] += 1
                    raise
                seconds = finish()
                record(name, args, kwargs, seconds, text_of(result))
                return result
            try:
                result = function(*args, **kwargs)
            except BaseException as error:
                record(name, args, kwargs, 0.0, '!raise ' + type(error).__name__)
                state[name]['raises'] += 1
                raise
            record(name, args, kwargs, 0.0, text_of(result))
            return result
        wrapper.__name__ = getattr(function, '__name__', name)
        wrapper.__wrapped__ = function
        return wrapper

    for name in names:
        if name in EXTRA:
            function = getattr(pyfunc, name)
            setattr(pyfunc, name, wrap(name, function))
    for cls_name, method in METHODS:
        if method in names:
            cls = getattr(pyfunc, cls_name)
            setattr(cls, method, wrap(method, getattr(cls, method)))
    for name in FUNCTIONS:
        if name in names:
            setattr(pyfunc, name, wrap(name, getattr(pyfunc, name)))

    def dump():
        payload = {'pid': os.getpid(), 'predicates': {}}
        for name, entry in state.items():
            keys = entry.pop('keys')
            distinct = len(keys)
            repeats = entry['calls'] - distinct
            payload['predicates'][name] = {
                'calls': entry['calls'], 'distinct': distinct, 'repeats': repeats,
                'changed': entry['changed'], 'changed_keys': len(entry['changed_keys']),
                'raises': entry['raises'], 'unhashable': entry['unhashable'],
                'own_s': round(entry['own'], 6),
                'cacheable_s': round(entry['cacheable'], 6),
            }
        try:
            with open(out_path, 'w', encoding='utf8') as handle:
                json.dump(payload, handle)
        except Exception:
            pass

    import atexit
    atexit.register(dump)


def _repr(result):
    try:
        text = repr(result)
    except BaseException:
        return '!unrepr'
    return text[:200]


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT * 1024, LIMIT * 1024))


def child_env(work, out_path, mode):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key not in ('PIPE_CC', 'PYTHONPATH')}
    site = Path(work) / 'site'
    site.mkdir(parents=True, exist_ok=True)
    (site / 'sitecustomize.py').write_text(SITECUSTOMIZE)
    env.update(PYTHONUTF8='1', PYTHONHASHSEED='0', AIL_SERVER='0', AIL_NO_CACHE='1',
               AIL_CACHE=str(Path(work) / 'cache'), TMPDIR=str(Path(work) / 'tmp'),
               PYTHONPATH=str(site), AILPRED_DIR=str(HERE), AILPRED_OUT=str(out_path),
               AILPRED_LIST=','.join(PREDICATES), AILPRED_MODE=mode)
    return env


def probe(source, out_path, mode='full', syntax=None, debug=False):
    work = tempfile.mkdtemp(prefix='ailpred-')
    out_path = str(Path(out_path).resolve())
    child_path = out_path + '.child.json'
    for stale in (child_path, child_path + '.err', out_path):
        try:
            os.unlink(stale)
        except OSError:
            pass
    for sub in ('cache', 'tmp'):
        (Path(work) / sub).mkdir(parents=True, exist_ok=True)
    env = child_env(work, child_path, mode)
    target = Path(work) / 'prog'
    source = Path(source).resolve()
    command = [sys.executable, '-X', 'utf8', '-B', str(AIL), 'compile', str(source),
               '-o', str(target)]
    if syntax:
        command += ['--syntax', syntax]
    if debug:
        command += ['--debug-dir', str(Path(work) / 'debug')]
    started = time.perf_counter()
    try:
        done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True,
                              timeout=1800, preexec_fn=limit_memory)
        returncode, stderr = done.returncode, done.stderr[-3000:]
    except subprocess.TimeoutExpired:
        returncode, stderr = -1, 'timeout'
    wall = time.perf_counter() - started
    data = None
    if Path(child_path).is_file():
        try:
            data = json.loads(Path(child_path).read_text(encoding='utf8'))
        except ValueError:
            data = None
    error = None
    if Path(child_path + '.err').is_file():
        error = Path(child_path + '.err').read_text(encoding='utf8')[:500]
    result = {'source': str(source), 'ok': returncode == 0, 'returncode': returncode,
              'wall_s': round(wall, 4), 'mode': mode, 'probe_error': error,
              'stderr': stderr, 'predicates': (data or {}).get('predicates', {})}
    if debug:
        c_path = Path(work) / 'debug' / 'program.c'
        result['program_c_sha'] = (_sha(c_path) if c_path.is_file() else None)
    shutil.rmtree(work, ignore_errors=True)
    Path(out_path).write_text(json.dumps(result, indent=1), encoding='utf8')
    return result


def _sha(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def corpus_inputs(limit=200):
    return sorted(CORPUS.glob('*/*.py'))[:limit]


def _read_rows(directory, names):
    rows = {}
    for name in names:
        path = Path(directory) / (name + '.json')
        if path.is_file():
            rows[name] = json.loads(path.read_text(encoding='utf8'))
    return rows


def build_report(probe_dir, corpus_dir, out_json, fe_path=None, lookup_ns=125.0):
    """Turn the per-input probe rows into ``CTIME_PRED.json``.

    The probe's own times are inflated by its wrapping, so the cacheable *fraction*
    ``probe_cacheable / probe_own`` is applied to the real front-end own time.  For a predicate
    row that ``CTIME_FE.json`` reports for a task, the scale is that task's
    ``fe_own / probe_own``; otherwise the pooled ``fe_own / probe_own`` fills the gap.  The
    fraction is scale-free, so this cannot report more cacheable time than the predicate's own
    time on a task whose row exists.
    """
    import datetime
    probe_dir = Path(probe_dir)
    fe_path = Path(fe_path) if fe_path else HERE / 'CTIME_FE.json'
    tasks = sorted(path.parent.name for path in SRC.glob('*/main.ail'))
    task_rows = _read_rows(probe_dir, tasks)
    missing = [task for task in tasks if task not in task_rows]
    if missing:
        raise SystemExit('missing probe rows: %s' % ', '.join(missing))
    corpus_path = Path(corpus_dir) / 'summary.json'
    if corpus_path.is_file():
        corpus_rows = json.loads(corpus_path.read_text(encoding='utf8'))
    else:
        corpus_rows = [json.loads(path.read_text(encoding='utf8'))
                       for path in sorted(Path(corpus_dir).glob('corpus-*.json'))
                       if '.child.' not in path.name]
    fe = json.loads(fe_path.read_text(encoding='utf8'))
    fe_own, walls = {}, {}
    for result in fe['results']:
        task = result['task']
        walls[task] = result['plain_summary']['wall']['median']
        fe_own[task] = {row['function']: row['own_s'] for row in result['profile']['top_own']}

    summary = []
    for name in PREDICATES:
        calls = repeats = changed = 0
        probe_own = probe_cacheable = 0.0
        fe_total = 0.0
        for task in tasks:
            row = task_rows[task]['predicates'].get(name)
            if row is None:
                continue
            calls += row['calls']
            repeats += row['repeats']
            changed += row['changed']
            probe_own += row['own_s']
            probe_cacheable += row['cacheable_s']
            fe_total += fe_own[task].get(name, 0.0)
        corpus_calls = sum(row['predicates'].get(name, {}).get('calls', 0) for row in corpus_rows)
        corpus_changed = sum(row['predicates'].get(name, {}).get('changed', 0) for row in corpus_rows)
        ratio = fe_total / probe_own if probe_own else 0.0
        summary.append({
            'predicate': name, 'calls': calls, 'repeats': repeats,
            'repeat_share': round(repeats / calls, 4) if calls else 0.0,
            'changed': changed, 'corpus_calls': corpus_calls,
            'changed_corpus': corpus_changed,
            'changed_all_inputs': changed + corpus_changed,
            'probe_own_s': round(probe_own, 6),
            'probe_cacheable_s': round(probe_cacheable, 6),
            'fe_own_s': round(fe_total, 6),
            'fe_probe_ratio': round(ratio, 6),
            'cacheable_s': round(probe_cacheable * ratio, 6),
            'eligible': changed + corpus_changed == 0,
        })
    listed = [row['predicate'] for row in
              sorted((row for row in summary if row['eligible']),
                     key=lambda row: row['cacheable_s'], reverse=True)]
    by_name = {row['predicate']: row for row in summary}

    task_out = []
    for task in tasks:
        probe = task_rows[task]['predicates']
        per = {}
        for name in PREDICATES:
            row = probe.get(name)
            if row is None:
                continue
            fe_task = fe_own[task].get(name)
            if fe_task is not None and row['own_s']:
                scale = fe_task / row['own_s']
            else:
                scale = by_name[name]['fe_probe_ratio']
            per[name] = {'calls': row['calls'], 'repeats': row['repeats'],
                         'changed': row['changed'],
                         'cacheable': round(row['cacheable_s'] * scale, 6)}
        wall = walls[task]

        def block(names):
            saving = sum(per[name]['cacheable'] - lookup_ns * 1e-9 * per[name]['calls']
                         for name in names if name in per)
            projection = 1.0 / (1.0 - saving / wall) if saving < wall else float('inf')
            return round(saving, 4), round(projection, 4), round(1 + (projection - 1) / 2, 4)

        saving_listed, projection_listed, halved_listed = block(listed)
        saving_all, projection_all, halved_all = block(PREDICATES)
        task_out.append({
            'task': task, 'wall': wall, 'predicates': per,
            'saving_listed': saving_listed, 'projection_listed': projection_listed,
            'halved_listed': halved_listed, 'saving_all': saving_all,
            'projection_all': projection_all, 'halved_all': halved_all,
        })

    record = {}
    out_path = Path(out_json)
    if out_path.is_file():
        try:
            record = json.loads(out_path.read_text(encoding='utf8'))
        except ValueError:
            record = {}
    record.update({
        'base': 'export of staging:integ (aea334f)',
        'date': datetime.date.today().isoformat(),
        'corpus_inputs': len(corpus_rows),
        'lookup_ns': lookup_ns,
        'lookup_s': lookup_ns * 1e-9,
        'predicate_summary': summary,
        'listed': listed,
        'tasks': task_out,
    })
    out_path.write_text(json.dumps(record, indent=1) + '\n', encoding='utf8')
    print('wrote %s: %d tasks, %d corpus inputs, listed %s'
          % (out_path, len(task_out), len(corpus_rows), ', '.join(listed)))
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--tasks', nargs='+', help='compare-task names under lab/compare/src')
    parser.add_argument('--corpus', action='store_true', help='first 200 sorted corpus programs')
    parser.add_argument('--out-dir')
    parser.add_argument('--mode', default='full', choices=('full', 'changed'))
    parser.add_argument('--source', help='one source file (Python syntax) instead of a task')
    parser.add_argument('--debug', action='store_true', help='also record sha256(program.c)')
    parser.add_argument('--report', metavar='PROBE_DIR',
                        help='build CTIME_PRED.json from probe rows instead of probing')
    parser.add_argument('--corpus-dir', help='probe directory of the 200 corpus rows')
    parser.add_argument('--out-json', default=str(HERE / 'CTIME_PRED.json'))
    parser.add_argument('--fe', default=str(HERE / 'CTIME_FE.json'))
    args = parser.parse_args(argv)
    if args.report:
        if not args.corpus_dir:
            parser.error('--report needs --corpus-dir')
        build_report(args.report, args.corpus_dir, args.out_json, args.fe)
        return 0
    if not args.out_dir:
        parser.error('--out-dir is required unless --report is given')
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if args.source:
        rows.append(probe(args.source, out_dir / (Path(args.source).stem + '.json'),
                          args.mode, 'python', args.debug))
    for task in args.tasks or ():
        source = SRC / task / 'main.ail'
        rows.append(probe(source, out_dir / (task + '.json'), args.mode, None, args.debug))
    if args.corpus:
        for index, source in enumerate(corpus_inputs(), 1):
            row = probe(source, out_dir / ('corpus-%03d.json' % index), 'changed', 'python')
            row['name'] = str(source.relative_to(CORPUS))
            rows.append(row)
            print('%3d %s ok=%s changed=%s' % (index, row['name'], row['ok'],
                  sum(p.get('changed', 0) for p in row['predicates'].values())), flush=True)
    summary = out_dir / 'summary.json'
    summary.write_text(json.dumps(rows, indent=1), encoding='utf8')
    failed = [row for row in rows if not row['ok']]
    print('rows=%d failed=%d summary=%s' % (len(rows), len(failed), summary))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
