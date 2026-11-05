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
from pathlib import Path
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
import os, sys, atexit, cProfile, time
_start = time.perf_counter()
_child = any(a.endswith('pyc.py') for a in sys.argv)
_parent = any(a.endswith(('ail_chatgpt.py', 'load_driver.py')) for a in sys.argv)
_stamp = os.environ.get('AILPROF_CHILD_TIME' if _child else 'AILPROF_PARENT_TIME')
if _stamp:
    def _stamp_exit():
        try:
            with open(_stamp, 'a', encoding='utf8') as handle:
                handle.write('%.6f\\n' % (time.perf_counter() - _start))
        except Exception:
            pass
    atexit.register(_stamp_exit)
_profile = None
if _child:
    _profile = os.environ.get('AILPROF_CHILD_PROFILE')
elif _parent:
    _profile = os.environ.get('AILPROF_PARENT_PROFILE')
if _profile:
    _p = cProfile.Profile(); _p.enable()
    def _dump():
        try:
            _p.disable(); _p.dump_stats(_profile)
        except Exception as error:
            sys.stderr.write('profile dump failed: %r\\n' % (error,))
    atexit.register(_dump)
# fe-profile: perf_counter wrappers around the front-end attempts, active only in the child.
# Importing pyfunc/pyboxed2 here (before pyc.py runs) is what lets pyc's `from pyfunc import
# to_c` bind the wrapper; the plain cold builds never see this branch.
_attempt_path = os.environ.get('AILPROF_ATTEMPTS')
_attempt_owner = os.getpid()
if _child and _attempt_path:
    try:
        _script = next((a for a in sys.argv if a.endswith('pyc.py')), None)
        if _script:
            _package = os.path.dirname(os.path.abspath(_script))
            if _package not in sys.path:
                sys.path.insert(0, _package)
        import pyfunc, pyboxed2, pymix
        _attempts = {'pid': _attempt_owner, 'argv': list(sys.argv), 'to_c': [],
                     'fe_jobs': [], 'fe_run_units': [], 'general_builds': [], 'analyze': []}
        def _rec(kind, row):
            _attempts[kind].append(row)
        _orig_to_c = pyfunc.to_c
        def _to_c(*args, **kwargs):
            frame = sys._getframe(1)
            row = {'caller': frame.f_code.co_name, 'framer': frame.f_code.co_filename,
                   'entry': kwargs.get('entry') or (args[4] if len(args) > 4 else None),
                   'name': kwargs.get('name') or (args[1] if len(args) > 1 else None),
                   'seconds': None, 'ok': None, 'error': None}
            started = time.perf_counter()
            try:
                result = _orig_to_c(*args, **kwargs)
            except BaseException as error:
                row['seconds'] = time.perf_counter() - started
                row['ok'] = False
                row['error'] = (type(error).__name__ + ': '
                                + ' '.join(str(error).split())[:300])
                _rec('to_c', row)
                raise
            row['seconds'] = time.perf_counter() - started
            row['ok'] = True
            _rec('to_c', row)
            return result
        pyfunc.to_c = _to_c
        _orig_jobs = pyfunc._fe_job_count
        def _job_count(nfns, info):
            jobs = _orig_jobs(nfns, info)
            _rec('fe_jobs', {'nfns': nfns, 'jobs': jobs})
            return jobs
        pyfunc._fe_job_count = _job_count
        _orig_run_units = pyfunc._fe_run_units
        def _run_units(units, jobs, classes, initial_symbols):
            started = time.perf_counter()
            try:
                return _orig_run_units(units, jobs, classes, initial_symbols)
            finally:
                _rec('fe_run_units', {'jobs': jobs, 'units': len(units),
                                      'seconds': time.perf_counter() - started})
        pyfunc._fe_run_units = _run_units
        _orig_general = pyboxed2.build
        def _general(source, report=None, allow_mix=True):
            started = time.perf_counter()
            try:
                text = _orig_general(source, report, allow_mix=allow_mix)
            except BaseException as error:
                _rec('general_builds', {'seconds': time.perf_counter() - started, 'ok': False,
                                        'mix_units': 0,
                                        'error': type(error).__name__ + ': '
                                                 + ' '.join(str(error).split())[:300]})
                raise
            _rec('general_builds', {
                'seconds': time.perf_counter() - started, 'ok': True,
                'mix_units': len(report.get('mix_units') or []) if isinstance(report, dict) else 0})
            return text
        pyboxed2.build = _general
        _orig_analyze = pymix.analyze
        def _analyze(source, classes=()):
            started = time.perf_counter()
            try:
                report = _orig_analyze(source, classes)
            except BaseException:
                _rec('analyze', {'seconds': time.perf_counter() - started, 'ok': False,
                                 'candidates': 0})
                raise
            _rec('analyze', {'seconds': time.perf_counter() - started, 'ok': True,
                             'candidates': len(getattr(report, 'candidates', {}) or {})})
            return report
        pymix.analyze = _analyze
        def _write_attempts():
            if os.getpid() != _attempt_owner:
                return                         # a forked AIL_FE_JOBS worker wrote nothing
            main = sys.modules.get('__main__')
            _attempts['fallback'] = getattr(main, 'last_fallback_reason', None)
            _attempts['fallback_line'] = getattr(main, 'last_fallback_line', None)
            try:
                import json
                with open(_attempt_path, 'w', encoding='utf8') as handle:
                    json.dump(_attempts, handle)
            except Exception:
                pass
        atexit.register(_write_attempts)
    except Exception as _hook_error:
        try:
            with open(_attempt_path + '.hook-error', 'w', encoding='utf8') as handle:
                handle.write(repr(_hook_error))
        except Exception:
            pass
'''

LOAD_DRIVER = '''\
import os, sys, time
sys.path.insert(0, os.environ['AIL_CTIME_ROOT'])
import ail_chatgpt
_orig = ail_chatgpt._load_sources
_stamp = os.environ.get('AILPROF_LOAD_TIME')
def _timed(*args, **kwargs):
    start = time.perf_counter()
    try:
        return _orig(*args, **kwargs)
    finally:
        if _stamp:
            with open(_stamp, 'a', encoding='utf8') as handle:
                handle.write('%.6f\\n' % (time.perf_counter() - start))
ail_chatgpt._load_sources = _timed
raise SystemExit(ail_chatgpt.main())
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


def env_for(work, fe=False, profile=None, fe_root=None, fe_log=None, parent_profile=None,
            attempts=None, extra_env=None):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key not in ('PIPE_CC', 'PYTHONPATH')}
    env.update(PYTHONUTF8='1', AIL_SERVER='0', AIL_NO_CACHE='1',
               AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'),
               PIPE_CC=str(WRAPPER), WRAP_CC=shutil.which('gcc') or 'gcc', WRAP_MODE='split',
               WRAP_LOG=str(work / 'cc.jsonl'), WRAP_SAVE_C=str(work / 'c'))
    site = work / 'site'
    site.mkdir(parents=True, exist_ok=True)
    (site / 'sitecustomize.py').write_text(SITECUSTOMIZE)
    env.update(PYTHONPATH=str(site), AILPROF_CHILD_TIME=str(work / 'child.time'),
               AILPROF_PARENT_TIME=str(work / 'parent.time'),
               AILPROF_LOAD_TIME=str(work / 'load.time'),
               AIL_CTIME_ROOT=str(AIL.parent))
    if fe:
        env.update(AIL_FE_CACHE='1', AIL_FE_CACHE_DIR=str(fe_root or (work / 'fe')),
                   AIL_FE_CACHE_LOG=str(fe_log or (work / 'fe.log')))
    if profile:
        env['AILPROF_CHILD_PROFILE'] = str(profile)
    if parent_profile:
        env['AILPROF_PARENT_PROFILE'] = str(parent_profile)
    if attempts:
        env['AILPROF_ATTEMPTS'] = str(attempts)
    if extra_env:
        env.update(extra_env)
    return env


def read_times(path):
    try:
        return round(sum(float(line) for line in Path(path).read_text().split()), 4)
    except (OSError, ValueError):
        return None


def build(source, out, work, fe=False, profile=None, fe_root=None, fe_log=None,
          parent_profile=None, attempts=None, extra_env=None):
    for sub in ('cache', 'tmp', 'c'):
        (work / sub).mkdir(parents=True, exist_ok=True)
    env = env_for(work, fe=fe, profile=profile, fe_root=fe_root, fe_log=fe_log,
                  parent_profile=parent_profile, attempts=attempts, extra_env=extra_env)
    rss = work / 'rss'
    driver = work / 'load_driver.py'
    driver.write_text(LOAD_DRIVER, encoding='utf8')
    command = ['/usr/bin/time', '-f', '%M', '-o', str(rss), sys.executable, '-X', 'utf8', '-B',
               str(driver), 'compile', str(source), '-o', str(out)]
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
    log_path = Path(fe_log) if fe_log else (work / 'fe.log')
    events = log_path.read_text().splitlines() if log_path.exists() else []
    child_s = read_times(work / 'child.time')
    load_s = read_times(work / 'load.time')
    return {'ok': done.returncode == 0, 'wall': round(wall, 4),
            'front': round(wall - compiled - linked, 4), 'compile': round(compiled, 4),
            'link': round(linked, 4),
            'parent_s': round(wall - child_s, 4) if child_s is not None else None,
            'child_s': child_s, 'load_s': load_s,
            'rss_kib': int(rss.read_text().split()[-1]) if rss.exists() else None,
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


def import_cost():
    """Seconds for a fresh child to import pyc (and everything pyc imports), bytecode warm."""
    package = REPO / 'AIL_CURRENT' / 'python' / 'pkg-v12'
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key != 'PYTHONPATH'}
    command = [sys.executable, '-X', 'utf8', '-c', 'import pyc']
    subprocess.run(command, cwd=str(package), env=env, capture_output=True)
    values = []
    for _ in range(3):
        started = time.perf_counter()
        subprocess.run(command, cwd=str(package), env=env, capture_output=True)
        values.append(time.perf_counter() - started)
    return round(min(values), 4)


def top_functions(path, count=15):
    stats = pstats.Stats(str(path))
    rows = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)
    result = []
    for func, (_cc, _nc, tottime, cumtime, _callers) in rows[:count]:
        name = '%s:%s' % (Path(func[0]).name, func[2]) if func[0] not in ('~', '<built-in>') else func[2]
        result.append({'function': name, 'cumtime': round(cumtime, 3), 'tottime': round(tottime, 3)})
    return result


def cumulative_of(path, fragment):
    stats = pstats.Stats(str(path))
    best = 0.0
    for func, (_cc, _nc, _tottime, cumtime, _callers) in stats.stats.items():
        if fragment in func[2]:
            best = max(best, cumtime)
    return best


def cumulative_function(path, name):
    stats = pstats.Stats(str(path))
    best = 0.0
    for func, (_cc, _nc, _tottime, cumtime, _callers) in stats.stats.items():
        if func[2] == name:
            best = max(best, cumtime)
    return best


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


GCC_MODULES = {'subprocess', 'select', 'selectors', 'fcntl', 'posix', 'threading',
               'socket', 'ssl', '_posixsubprocess'}
GCC_FUNCTIONS = {'_cc', 'run_cc', 'communicate', 'wait', 'poll', '_fe_compile',
                 '_fe_compile_multi', '_finalize_output'}


def module_of(func):
    source = func[0]
    if source in ('~', '<built-in>') or source.startswith('<'):
        return 'builtins' if source in ('~', '<built-in>') else source.strip('<>')
    return pathlib.Path(source).stem


def is_gcc_row(row):
    return row['module'] in GCC_MODULES or row['function'] in GCC_FUNCTIONS


def profile_rows(path):
    """Own time by function, with C functions charged to their callers.

    cProfile parks the gcc wait in builtins (`select.poll`, `posix.read`), so keeping C rows
    would book gcc to the front end.  Like `profile_phases`, each C function's own time is split
    over its callers by the time each spent in it; the rows below are therefore Python functions
    (or an unattributed C row) and the gcc modules can be removed by name."""
    stats = pstats.Stats(str(path))
    rows = {}
    for func, (_cc, _nc, tottime, cumtime, callers) in stats.stats.items():
        module = module_of(func)
        if func[0].endswith('.py'):
            row = rows.setdefault(func, {'module': module, 'function': func[2],
                                        'file': func[0], 'line': func[1],
                                        'tottime': 0.0, 'cumtime': cumtime})
            row['tottime'] += tottime
            row['cumtime'] = max(row['cumtime'], cumtime)
            continue
        total = sum(entry[2] for entry in callers.values()) or 0.0
        if total:
            for caller, (_calls, _ncalls, time_in_callee, _ctime) in callers.items():
                row = rows.setdefault(caller, {'module': module_of(caller),
                                               'function': caller[2], 'file': caller[0],
                                               'line': caller[1], 'tottime': 0.0,
                                               'cumtime': 0.0})
                row['tottime'] += tottime * time_in_callee / total
        else:
            row = rows.setdefault(func, {'module': module, 'function': func[2],
                                        'file': func[0], 'line': func[1],
                                        'tottime': 0.0, 'cumtime': cumtime})
            row['tottime'] += tottime
    return list(rows.values())


def profile_fe(path, child_non_gcc):
    """Scale profiled own time onto the un-profiled front-end wall.

    cProfile also sees the child's wait inside gcc (subprocess/select), so those modules and the
    pyc compile wrappers are taken out before scaling.  The remaining own time is the front end;
    every named row below is a fraction of child_non_gcc, so the rows add up to it."""
    rows = profile_rows(path)
    total = sum(row['tottime'] for row in rows)
    excluded = sum(row['tottime'] for row in rows if is_gcc_row(row))
    front = max(total - excluded, 1e-9)
    scale = (child_non_gcc / front) if child_non_gcc else 1.0
    for row in rows:
        row['own_s'] = round(row['tottime'] * scale, 6)
        row['cum_s'] = round(row['cumtime'] * scale, 6)
        row['gcc'] = is_gcc_row(row)
    front_rows = [row for row in rows if not row['gcc']]
    own_top = sorted(front_rows, key=lambda row: row['tottime'], reverse=True)[:25]
    cum_top = sorted(front_rows, key=lambda row: row['cumtime'], reverse=True)[:25]
    top25 = sum(row['tottime'] for row in own_top)
    modules = {}
    for row in front_rows:
        modules[row['module']] = modules.get(row['module'], 0.0) + row['own_s']
    return {'profiled_total_s': round(total, 4), 'profiled_front_s': round(front, 4),
            'gcc_excluded_s': round(excluded, 4), 'scale': round(scale, 4),
            'child_non_gcc': round(child_non_gcc, 4),
            'top25_own_share': round(top25 / front, 4),
            'attributed_own_s': round(sum(row['own_s'] for row in front_rows), 4),
            'attributed_share': round(sum(row['own_s'] for row in front_rows)
                                      / child_non_gcc, 4) if child_non_gcc else None,
            'top_own': own_top, 'top_cum': cum_top,
            'modules': {key: round(value, 4)
                        for key, value in sorted(modules.items(), key=lambda item: -item[1])}}


def attempt_summary(attempts):
    rows = attempts.get('to_c') or []
    def typed(row):
        return (pathlib.Path(row.get('framer') or '').name == 'pyc.py'
                and row.get('caller') in ('to_c', '_to_c', '_build_unshadowed_inner',
                                          '_build_unshadowed_exact'))
    typed_fail = [row for row in rows if typed(row) and not row.get('ok')]
    typed_ok = [row for row in rows if typed(row) and row.get('ok')]
    candidate = [row for row in rows if row.get('caller') == '_setup_mix']
    general = attempts.get('general_builds') or []
    units = attempts.get('fe_run_units') or []
    jobs = attempts.get('fe_jobs') or []
    fallback = attempts.get('fallback')
    path = 'typed'
    if fallback:
        path = 'general'
    if any(row.get('mix_units') for row in general):
        path = 'mixed'
    parallel = [row for row in units if row.get('jobs', 1) > 1]
    worker = max((row['jobs'] for row in parallel), default=1)
    nfns = max((row.get('nfns') or 0 for row in jobs), default=0)
    note = None
    if fallback:
        note = ('built on the general path because '
                + ' '.join(str(fallback).split()).rstrip(';'))
    wasted = sum(row['seconds'] for row in typed_fail)
    wasted += sum(row['seconds'] for row in candidate if not row.get('ok'))
    return {'path': path, 'fallback': fallback, 'fallback_note': note,
            'parallel': bool(parallel), 'workers': worker if parallel else 1,
            'functions': nfns if nfns else None,
            'typed_attempts': typed_ok + typed_fail,
            'typed_refusals': typed_fail, 'pymix_candidates': candidate,
            'general_builds': general, 'analyze': attempts.get('analyze') or [],
            'fe_jobs': jobs, 'fe_run_units': units,
            'wasted_s': round(wasted, 4),
            'candidate_s': round(sum(row['seconds'] for row in candidate), 4),
            'typed_s': round(sum(row['seconds'] for row in typed_ok + typed_fail), 4),
            'general_s': round(sum(row['seconds'] for row in general), 4)}


def fe_one_task(task, runs, root):
    source = SRC / task / 'main.ail'
    result = {'task': task, 'plain': [], 'wrapped': [], 'profile': None,
              'attempts': None, 'path': None, 'fallback': None, 'fallback_note': None}
    for index in range(runs):
        work = root / ('%s-fe-plain-%d' % (task, index))
        plain = build(source, work / 'prog', work)
        plain['child_non_gcc'] = round(max((plain['child_s'] or 0.0) - plain['compile']
                                           - plain['link'], 0.0), 4)
        result['plain'].append(plain)
        work = root / ('%s-fe-wrap-%d' % (task, index))
        log = work / 'attempts.json'
        wrapped = build(source, work / 'prog', work, attempts=log)
        wrapped['child_non_gcc'] = round(max((wrapped['child_s'] or 0.0) - wrapped['compile']
                                             - wrapped['link'], 0.0), 4)
        wrapped['attempts'] = None
        if log.exists():
            try:
                wrapped['attempts'] = json.loads(log.read_text())
            except ValueError:
                pass
        result['wrapped'].append(wrapped)
    plain_ok = [row for row in result['plain'] if row['ok']]
    wrap_ok = [row for row in result['wrapped'] if row['ok']]
    if not plain_ok or not wrap_ok:
        result['error'] = (plain_ok or result['plain'])[0].get('stderr', '')
        return result
    result['plain_summary'] = {key: summary([row[key] for row in result['plain']])
                               for key in ('wall', 'front', 'compile', 'link', 'child_s',
                                           'child_non_gcc', 'rss_kib')}
    result['wrapped_summary'] = {key: summary([row[key] for row in result['wrapped']])
                                 for key in ('wall', 'front', 'compile', 'link', 'child_s',
                                             'child_non_gcc', 'rss_kib')}
    last = result['wrapped'][-1].get('attempts')
    if last:
        result['attempts'] = attempt_summary(last)
        result['path'] = result['attempts']['path']
        result['fallback'] = result['attempts']['fallback']
        result['fallback_note'] = result['attempts']['fallback_note']
    else:
        result['path'] = 'typed' if 'built on the general path' not in result['wrapped'][-1]['stderr'] else 'general'
        result['fallback_note'] = ('built on the general path'
                                   if result['path'] == 'general' else None)
    work = root / ('%s-fe-profile' % task)
    prof = build(source, work / 'prog', work, profile=work / 'child.prof')
    profiled_non_gcc = round(max((prof['child_s'] or 0.0) - prof['compile']
                                 - prof['link'], 0.0), 4)
    child_non_gcc = result['plain_summary']['child_non_gcc']['median'] or profiled_non_gcc
    entry = {'ok': False, 'child_non_gcc': child_non_gcc,
             'profiled_child_non_gcc': profiled_non_gcc, 'stderr': prof['stderr']}
    if prof['ok'] and (work / 'child.prof').exists():
        entry = profile_fe(work / 'child.prof', child_non_gcc)
        entry.update(ok=True, wall=prof['wall'], child_s=prof['child_s'],
                     compile_s=prof['compile'], link_s=prof['link'],
                     profiled_child_non_gcc=profiled_non_gcc)
        child_plain = result['plain_summary']['child_s']['median']
        child_prof = prof['child_s']
        entry['plain_child_s'] = round(child_plain, 4) if child_plain else None
        entry['profiled_child_s'] = round(child_prof, 4) if child_prof else None
        entry['stop_rule_ratio'] = round(child_prof / child_plain, 3) if child_plain else None
        entry['stop_rule'] = bool(child_plain and child_prof / child_plain > 2.0)
    result['profile'] = entry
    # AIL_FE_JOBS profiles only the parent: with 4 workers the cProfile above sees the pipe
    # (`connection._recv`) instead of the function bodies.  One serial profile attributes the
    # same work, scaled to a serial plain build of the same task.
    if (result.get('attempts') or {}).get('workers', 1) > 1:
        serial_env = {'AIL_FE_JOBS': '1'}
        work = root / ('%s-fe-serial-plain' % task)
        plain_serial = build(source, work / 'prog', work, extra_env=serial_env)
        serial_non_gcc = round(max((plain_serial['child_s'] or 0.0) - plain_serial['compile']
                                   - plain_serial['link'], 0.0), 4)
        work = root / ('%s-fe-serial-profile' % task)
        ser = build(source, work / 'prog', work, profile=work / 'child.prof',
                    extra_env=serial_env)
        serial_entry = {'ok': False, 'child_non_gcc': serial_non_gcc,
                        'stderr': ser['stderr']}
        if ser['ok'] and (work / 'child.prof').exists():
            serial_entry = profile_fe(work / 'child.prof', serial_non_gcc)
            serial_entry.update(ok=True, wall=ser['wall'], child_s=ser['child_s'],
                                compile_s=ser['compile'], link_s=ser['link'],
                                plain_child_s=round(plain_serial['child_s'], 4),
                                profiled_child_s=round(ser['child_s'], 4))
            serial_entry['stop_rule_ratio'] = round(ser['child_s'] / plain_serial['child_s'], 3) \
                if plain_serial['child_s'] else None
            serial_entry['stop_rule'] = bool(plain_serial['child_s']
                                             and ser['child_s'] / plain_serial['child_s'] > 2.0)
        result['profile_serial'] = serial_entry
    return result


def one_task(task, runs, root, do_profile):
    source = SRC / task / 'main.ail'
    result = {'task': task, 'cold': [], 'fecache': [], 'profile': None, 'hit_profile': None}
    for index in range(runs):
        work = root / ('%s-cold-%d' % (task, index))
        result['cold'].append(build(source, work / 'prog', work))
    ok = [row for row in result['cold'] if row['ok']]
    if not ok:
        result['error'] = result['cold'][0]['stderr']
        return result
    result['import_s'] = import_cost()
    result['cold_summary'] = {key: summary([row[key] for row in result['cold']])
                              for key in ('wall', 'front', 'compile', 'link', 'parent_s',
                                          'child_s', 'load_s', 'rss_kib', 'binary', 'c_bytes')}
    result['gcc_split'] = gcc_split(pathlib.Path(ok[-1]['work']), source)

    for index in range(runs):
        work = root / ('%s-fe-%d' % (task, index))
        fe_root, fe_log = work / 'fe', work / 'fe.log'
        first = build(source, work / 'cold' / 'prog', work / 'cold', fe=True,
                      fe_root=fe_root, fe_log=fe_log)
        second = build(source, work / 'warm' / 'prog', work / 'warm', fe=True,
                       fe_root=fe_root, fe_log=fe_log)
        last = second['events'][-1] if second['events'] else ''
        if not last.startswith('hit'):
            raise RuntimeError('%s run %d: expected a front-end cache hit, log says %r'
                               % (task, index, last))
        result['fecache'].append({'cold': first, 'hit': second})
    good = [row for row in result['fecache'] if row['cold']['ok'] and row['hit']['ok']]
    result['fecache_summary'] = {
        'cold': {key: summary([row['cold'][key] for row in good])
                 for key in ('wall', 'front', 'compile', 'link', 'parent_s', 'child_s')},
        'hit': {key: summary([row['hit'][key] for row in good])
                for key in ('wall', 'front', 'compile', 'link', 'parent_s', 'child_s')},
        'hit_events': [row['hit']['events'][-1] if row['hit']['events'] else None for row in good]}

    if do_profile:
        work = root / ('%s-profile' % task)
        profile, parentp = work / 'child.prof', work / 'parent.prof'
        built = build(source, work / 'prog', work, profile=profile, parent_profile=parentp)
        result['profile'] = {'ok': False, 'stderr': built['stderr']}
        if built['ok'] and profile.exists():
            shares, total = profile_phases(profile)
            child_non_gcc = max((built['child_s'] or 0.0) - built['compile'] - built['link'], 0.0)
            entry = {'ok': True, 'shares': shares, 'profiled_s': total,
                     'child_non_gcc': round(child_non_gcc, 4),
                     'phases_s': {key: round(value * child_non_gcc, 4)
                                  for key, value in shares.items()},
                     'top': top_functions(profile)}
            if parentp.exists():
                pshares, ptotal = profile_phases(parentp)
                parent_wall = result['cold_summary']['parent_s']['median']
                load = result['cold_summary']['load_s']['median'] or 0.0
                entry.update(parent_s=round(parent_wall, 4), parent_profiled_s=ptotal,
                             load_sources_s=round(load, 4),
                             parent_other_s=round(max(parent_wall - load, 0.0), 4))
            result['profile'] = entry

        work = root / ('%s-hit-profile' % task)
        fe_root, fe_log = work / 'fe', work / 'fe.log'
        first = build(source, work / 'cold' / 'prog', work / 'cold', fe=True,
                      fe_root=fe_root, fe_log=fe_log)
        profile = work / 'hit.prof'
        second = build(source, work / 'warm' / 'prog', work / 'warm', fe=True,
                       fe_root=fe_root, fe_log=fe_log, profile=profile)
        last = second['events'][-1] if second['events'] else ''
        if first['ok'] and second['ok'] and last.startswith('hit') and profile.exists():
            shares, total = profile_phases(profile)
            child_non_gcc = max((second['child_s'] or 0.0) - second['compile'] - second['link'], 0.0)
            result['hit_profile'] = {'ok': True, 'shares': shares, 'profiled_s': total,
                                     'wall': second['wall'],
                                     'child_non_gcc': round(child_non_gcc, 4),
                                     'phases_s': {key: round(value * child_non_gcc, 4)
                                                  for key, value in shares.items()},
                                     'top': top_functions(profile, 10)}
        else:
            result['hit_profile'] = {'ok': False, 'event': last, 'stderr': second['stderr']}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tasks', default=','.join(TASKS))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--out', default=None)
    parser.add_argument('--no-profile', dest='profile', action='store_false')
    parser.add_argument('--fe-profile', action='store_true',
                        help='time front-end attempts and profile the child front end')
    args = parser.parse_args()
    tasks = [task.strip() for task in args.tasks.split(',') if task.strip()]
    out = args.out or str(HERE / ('CTIME_FE.json' if args.fe_profile else 'CTIME_2026-11.json'))
    root = pathlib.Path(tempfile.mkdtemp(prefix='ail-ctime-'))
    started = time.time()
    result = {'date': time.strftime('%Y-%m-%d'), 'runs': args.runs, 'limit_kib': LIMIT, 'tasks': tasks,
              'work': str(root), 'results': []}
    for task in tasks:
        if args.fe_profile:
            row = fe_one_task(task, args.runs, root)
            result['results'].append(row)
            print(task, row.get('path'),
                  json.dumps(row.get('plain_summary', {}).get('child_s')),
                  'attempts=%.3fs' % (row.get('attempts') or {}).get('wasted_s', 0.0),
                  file=sys.stderr, flush=True)
        else:
            row = one_task(task, args.runs, root, args.profile)
            result['results'].append(row)
            print(task, json.dumps(row.get('cold_summary', {}).get('wall')), file=sys.stderr, flush=True)
    result['elapsed_s'] = round(time.time() - started, 1)
    pathlib.Path(out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print('wrote', out, 'in %.1fs' % result['elapsed_s'], file=sys.stderr)
    if args.fe_profile:
        return 0 if all(row.get('plain_summary') for row in result['results']) else 1
    return 0 if all(row.get('cold_summary') for row in result['results']) else 1


if __name__ == '__main__':
    sys.exit(main())
