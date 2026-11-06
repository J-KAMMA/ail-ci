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

    python3 lab/profile/pred_probe.py --tasks berth_sim chain_relax tally_lang --out-dir /tmp/pred
    python3 lab/profile/pred_probe.py --corpus --out-dir /tmp/pred
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


def _token(value, alive):
    """A hashable key token: the value for a primitive, ``id()`` for anything else.

    Keeping the object in ``alive`` is what stops CPython reusing its id, so two different
    calls cannot collide by accident."""
    if _primitive(value):
        return ('lit', value)
    alive.append(value)
    return ('id', id(value))


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--tasks', nargs='+', help='compare-task names under lab/compare/src')
    parser.add_argument('--corpus', action='store_true', help='first 200 sorted corpus programs')
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--mode', default='full', choices=('full', 'changed'))
    parser.add_argument('--source', help='one source file (Python syntax) instead of a task')
    parser.add_argument('--debug', action='store_true', help='also record sha256(program.c)')
    args = parser.parse_args(argv)
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
