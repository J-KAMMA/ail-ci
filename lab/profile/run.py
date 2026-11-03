#!/usr/bin/env python3
"""Where a cold build's time goes: the ten lab/compare tasks, median of --runs, ulimit -v 1500000.

Each build gets a fresh AIL_CACHE and TMPDIR.  Every C compiler call goes through
lab/fecache/cc_wrap.py, which splits one driver compile+link into `-c` and a link and records
the time of each, so Python = wall - compile - link.  The saved C is then split at the runtime
prelude boundary and both parts are compiled again with the build's own flags to price gcc's
prelude share.  A cProfile run of the same CLI, profiled inside the pyc.py child, apportions
the Python wall over module buckets (front end / IR / C generation / startup).

    python3 lab/profile/run.py --runs 3 --out lab/profile/CTIME_2026-11.json
"""
import argparse
import atexit
import hashlib
import json
import os
import pathlib
import pstats
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
SRC = REPO / 'lab' / 'compare' / 'src'
WRAPPER = REPO / 'lab' / 'fecache' / 'cc_wrap.py'
TASKS = tuple(sorted(path.parent.name for path in SRC.glob('*/main.ail')))
LIMIT = 1500000

SITECUSTOMIZE = '''\
import os, sys, atexit, cProfile
if os.environ.get('AIL_PROFILE_OUT') and any(a.endswith('pyc.py') for a in sys.argv):
    _p = cProfile.Profile(); _p.enable()
    def _dump():
        try:
            _p.disable(); _p.dump_stats(os.environ['AIL_PROFILE_OUT'])
        except Exception as error:
            sys.stderr.write('profile dump failed: %r\\n' % (error,))
    atexit.register(_dump)
'''

# module -> phase.  pyfunc is the front end AND the legacy typed emitter; every profile so far
# spends it on analysis, so it is the front end bucket and the report says so.  pyboxed2/cruntime
# assemble the general path's C text; ir/* is the unified IR's lowering, passes, verification
# and emission.
FRONT = {'pyfunc', 'pyfront', 'fastwalk', 'shadowing', 'bigcap', 'biggate', 'intmode',
         'rangecheck', 'pymix', 'boolkind', 'numidentity', 'unbound', 'modtables', 'pyc',
         'pipeline', 'callable_types', 'sortkeys', 'typedforms', 'nested_lists', 'aliasrefuse',
         'dunders', 'dunderrt', 'classname', 'walkmemo', 'bigint_core', 'bigint_obj', 'ccsplit',
         'mix', 'pymix', 'tupcommon', 'tuplegen', 'safetyrt', 'genlib', 'filelib', 'iterlower',
         'hashlower', 'matchlower', 'pathlower', 'boxclosure', 'typedpar', 'threadlib'}
IR = {'ir', 'driver', 'lower', 'lower_text', 'emit_c', 'emit_text', 'effects', 'flowtypes',
      'ifadd', 'ownership', 'rtc', 'text', 'verify', 'walias', 'passes', 'mem2reg', 'licm',
      'simplify', 'ranges', 'symbounds', 'unified'}
CGEN = {'cruntime', 'pyboxed2', 'filert', 'clockrt', 'dtrt', 'dunderrt', 'classname',
        'safetyrt', 'threadrt', 'jsonrt', 'csvgen'}


def phase_of(func):
    module = func[0]
    if '.py' in module:
        module = pathlib.Path(module).stem
    if module in IR:
        return 'ir'
    if module in CGEN:
        return 'cgen'
    if module in FRONT:
        return 'front'
    return 'startup'


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT * 1024, LIMIT * 1024))


def env_for(work, fe=False, profile=None):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key not in ('PIPE_CC', 'PYTHONPATH')}
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', AIL_SERVER='0', AIL_NO_CACHE='1',
               AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'),
               PIPE_CC=str(WRAPPER), WRAP_CC=shutil.which('gcc') or 'gcc', WRAP_MODE='split',
               WRAP_LOG=str(work / 'cc.jsonl'), WRAP_SAVE_C=str(work / 'c'))
    if fe:
        env.update(AIL_FE_CACHE='1', AIL_FE_CACHE_DIR=str(work / 'fe'),
                   AIL_FE_CACHE_LOG=str(work / 'fe.log'))
    if profile:
        site = work / 'site'
        site.mkdir()
        (site / 'sitecustomize.py').write_text(SITECUSTOMIZE)
        env.update(PYTHONPATH=str(site), AIL_PROFILE_OUT=str(profile))
    return env


def build(source, out, work, fe=False, profile=None):
    for sub in ('cache', 'tmp', 'c'):
        (work / sub).mkdir(parents=True, exist_ok=True)
    env = env_for(work, fe=fe, profile=profile)
    rss = work / 'rss'
    command = ['/usr/bin/time', '-f', '%M', '-o', str(rss), sys.executable, '-X', 'utf8', '-B',
               str(AIL), 'compile', str(source), '-o', str(out)]
    started = time.perf_counter()
    done = subprocess.run(command, cwd=str(work), env=env, capture_output=True, text=True,
                          timeout=1800, preexec_fn=limit_memory)
    wall = time.perf_counter() - started
    rows = []
    log = work / 'cc.jsonl'
    if log.exists():
        rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    compiled = sum(row.get('compile') or 0.0 for row in rows)
    linked = sum(row.get('link') or 0.0 for row in rows)
    events = (work / 'fe.log').read_text().splitlines() if (work / 'fe.log').exists() else []
    return {'ok': done.returncode == 0, 'wall': round(wall, 4),
            'front': round(wall - compiled - linked, 4), 'compile': round(compiled, 4),
            'link': round(linked, 4), 'rss_kib': int(rss.read_text().split()[-1]) if rss.exists() else None,
            'events': events, 'stderr': done.stderr[-2000:] if done.returncode else '',
            'binary': out.stat().st_size if out.is_file() else 0,
            'c_bytes': sum(path.stat().st_size for path in (work / 'c').glob('*.c'))
                       if (work / 'c').is_dir() else 0,
            'work': str(work)}


def summary(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return {'median': round(statistics.median(values), 4), 'min': round(min(values), 4),
            'max': round(max(values), 4), 'n': len(values)}


def profile_phases(path):
    """Own time by phase.  C functions (isinstance, getattr, ...) are attributed to their
    callers in proportion to the time each caller spent in them, so the buckets are compiler
    phases rather than a large `builtins` slice."""
    stats = pstats.Stats(str(path))
    own = {}
    for func, (_cc, _nc, tottime, _ct, callers) in stats.stats.items():
        module = func[0]
        if module.startswith('<') or module == '~' or not module.endswith('.py'):
            total = sum(entry[2] for entry in callers.values()) or 0.0
            if total:
                for caller, (_calls, _ncalls, time_in_callee, _ctime) in callers.items():
                    own[phase_of(caller)] = own.get(phase_of(caller), 0.0) \
                        + tottime * time_in_callee / total
            else:
                own['startup'] = own.get('startup', 0.0) + tottime
        else:
            own[phase_of(func)] = own.get(phase_of(func), 0.0) + tottime
    total = sum(own.values())
    return {key: round(value / total, 4) for key, value in own.items()}, round(total, 3)


def function_names(source):
    text = source.read_text(encoding='utf-8')
    names = set(re.findall(r'(?m)^\s*(?:fn|def)\s+([A-Za-z_]\w*)', text))
    names.add('main')
    return names


def prelude_split(c_file, source):
    text = c_file.read_text(encoding='utf-8')
    marker = '/* ---- interned attribute-name ids ---- */'
    if marker in text:
        return text.split(marker, 1)[0]
    names = function_names(source)
    declaration = re.compile(
        r'^(?:(?:static|inline|extern)\s+)*'
        r'(?:void|int|int64_t|uint\w*|double|float|bool|char|ail_\w+(?:\s*\*)?)\s+'
        r'([A-Za-z_]\w*)\s*\(')
    position = 0
    for line in text.splitlines(True):
        match = declaration.match(line)
        if match and match.group(1) in names:
            return text[:position]
        position += len(line)
    return text[:len(text) // 2]


def cpu_of(command):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    done = subprocess.run(command, capture_output=True, text=True)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return (after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime,
            done.returncode, done.stderr[-400:])


def gcc_split(work, source):
    cs = sorted((work / 'c').glob('*.c'))
    if not cs:
        return None
    c_file = max(cs, key=lambda path: path.stat().st_size)
    rows = [json.loads(line) for line in (work / 'cc.jsonl').read_text().splitlines()
            if line.strip()]
    flags = []
    for row in rows:
        for arg in row.get('args') or []:
            if arg.startswith(('-O', '-f', '-m')) and not arg.startswith('-fdiagnostics'):
                if arg not in flags:
                    flags.append(arg)
        if '-pthread' in (row.get('args') or []) and '-pthread' not in flags:
            flags.append('-pthread')
    prelude = prelude_split(c_file, source)
    pre = work / 'prelude.c'
    pre.write_text(prelude, encoding='utf-8')
    full_obj = work / 'full.o'
    pre_obj = work / 'prelude.o'
    best = lambda cmd: min(cpu_of(cmd)[0] for _ in range(3))
    full = best(['gcc', *flags, '-w', '-c', '-o', str(full_obj), str(c_file)])
    prelude_only = best(['gcc', *flags, '-w', '-c', '-o', str(pre_obj), str(pre)])
    syntax = best(['gcc', *flags, '-w', '-fsyntax-only', str(c_file)])
    return {'flags': flags, 'c_bytes': c_file.stat().st_size,
            'prelude_bytes': len(prelude), 'prelude_share_bytes': round(len(prelude) / c_file.stat().st_size, 4),
            'full_c': round(full, 4), 'prelude_c': round(prelude_only, 4),
            'prelude_share': round(prelude_only / full, 4) if full else None,
            'syntax_c': round(syntax, 4)}


def one_task(task, runs, root, do_profile):
    source = SRC / task / 'main.ail'
    result = {'task': task, 'cold': [], 'fecache': [], 'profile': None}
    for index in range(runs):
        work = root / ('%s-cold-%d' % (task, index))
        result['cold'].append(build(source, work / 'prog', work))
    ok = [row for row in result['cold'] if row['ok']]
    if not ok:
        result['error'] = result['cold'][0]['stderr']
        return result
    result['cold_summary'] = {key: summary([row[key] for row in result['cold']])
                              for key in ('wall', 'front', 'compile', 'link', 'rss_kib',
                                          'binary', 'c_bytes')}
    result['gcc_split'] = gcc_split(pathlib.Path(ok[-1]['work']), source)

    for index in range(runs):
        work = root / ('%s-fe-%d' % (task, index))
        first = build(source, work / 'cold' / 'prog', work / 'cold', fe=True)
        second = build(source, work / 'warm' / 'prog', work / 'warm', fe=True)
        result['fecache'].append({'cold': first, 'hit': second})
    good = [row for row in result['fecache'] if row['cold']['ok'] and row['hit']['ok']]
    result['fecache_summary'] = {
        'cold': {key: summary([row['cold'][key] for row in good])
                 for key in ('wall', 'front', 'compile', 'link')},
        'hit': {key: summary([row['hit'][key] for row in good])
                for key in ('wall', 'front', 'compile', 'link')},
        'hit_events': [row['hit']['events'][-1] if row['hit']['events'] else None for row in good]}

    if do_profile:
        work = root / ('%s-profile' % task)
        profile = work / 'profile.out'
        built = build(source, work / 'prog', work, profile=profile)
        if built['ok'] and profile.exists():
            shares, total = profile_phases(profile)
            result['profile'] = {'ok': True, 'shares': shares, 'profiled_s': total,
                                 'python_wall': built['front'],
                                 'phases_s': {key: round(value * built['front'], 4)
                                              for key, value in shares.items()}}
        else:
            result['profile'] = {'ok': False, 'stderr': built['stderr']}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tasks', default=','.join(TASKS))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--out', default=str(HERE / 'CTIME_2026-11.json'))
    parser.add_argument('--no-profile', dest='profile', action='store_false')
    args = parser.parse_args()
    tasks = [task.strip() for task in args.tasks.split(',') if task.strip()]
    root = pathlib.Path(tempfile.mkdtemp(prefix='ail-ctime-'))
    started = time.time()
    result = {'date': '2026-11-03', 'runs': args.runs, 'limit_kib': LIMIT, 'tasks': tasks,
              'work': str(root), 'results': []}
    for task in tasks:
        row = one_task(task, args.runs, root, args.profile)
        result['results'].append(row)
        print(task, json.dumps(row.get('cold_summary', {}).get('wall')), file=sys.stderr, flush=True)
    result['elapsed_s'] = round(time.time() - started, 1)
    pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print('wrote', args.out, 'in %.1fs' % result['elapsed_s'], file=sys.stderr)
    return 0 if all(row.get('cold_summary') for row in result['results']) else 1


if __name__ == '__main__':
    sys.exit(main())
