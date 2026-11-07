#!/usr/bin/env python3
"""Measure where AIL's Python front end spends compile time.

The compiler is not changed.  This harness only invokes the public CLI
(`ail_chatgpt.py compile`) and profiles the two Python processes it starts
(the outer driver and `python/pkg-v12/pyc.py`) with a `sitecustomize.py` that
turns cProfile on and writes one pstats file per process.

    python3 lab/fe/prof.py --out lab/fe/results.json

Sample, as asked by the task:
  * the ten `lab/compare/src/<task>/main.py` and their `typed.py`;
  * the fourteen programs timed in `lab/tcc/RESULTS.md` (the two compare
    programs above plus twelve `corpus/gdev` programs).

Per program, cold (fresh `AIL_CACHE`, `AIL_NO_CACHE=1`):
  * wall clock, median of `--reps` (default 3);
  * `/usr/bin/time -v` peak RSS (one run);
  * one cProfile run, split into outer/inner process stats;
  * `python3 -X importtime` totals for the outer and inner entry points.

Warm: a first run fills `AIL_CACHE`, a second (median of 3) is timed and
profiled, so the table says what still runs on a cache hit.

The phases reported for the cold build are the driver's own top-level
functions (their names are in `PASS_FUNCS` below).  The typed and general
emitters interleave type analysis with writing the C string; the harness
reports each emitter whole (analysis + C emission) rather than pretending
they can be separated without changing the compiler.  `_cc` is the C
compile/link subprocess.
"""
import argparse
import json
import os
import pathlib
import platform
import pstats
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
PYC = REPO / 'AIL_CURRENT' / 'python' / 'pkg-v12' / 'pyc.py'
TIMED_OUTER = HERE / 'timed_outer.py'
TIMED_INNER = HERE / 'timed_inner.py'
COMPARE = REPO / 'lab' / 'compare' / 'src'
CORPUS = REPO / 'corpus' / 'gdev'

# The fourteen programs timed in lab/tcc/RESULTS.md (2 compare + 12 corpus).
TCC14 = ('berth_sim', 'echo_pack', 'g17_004', 'g05_030', 'g14_014', 'g00_034',
         'g18_008', 'g00_036', 'g04_006', 'g14_004', 'g19_028', 'g02_014',
         'g23_036', 'g10_010')

# Top-level driver functions that mark a pass boundary.
PASS_FUNCS = {
    'load_sources': ('ail_chatgpt.py', '_load_sources'),
    'ffi_session': ('ail_chatgpt.py', '_ffi_session'),
    'frontend_key': ('ail_chatgpt.py', '_build_cache'),
    'fold_int_constants': ('pyfront.py', 'fold_int_constants'),
    'refuse_static_big_calls': ('pyc.py', '_refuse_static_big_calls'),
    'python_defs_only_runs_nothing': ('pyc.py', '_python_defs_only_runs_nothing'),
    'refuse_big_capable': ('pyc.py', '_refuse_big_capable'),
    'refuse_typed_big_store': ('pyc.py', '_refuse_typed_big_store'),
    'typed_emit': ('pyc.py', 'to_c'),
    'func_typed_emit': ('pyfunc.py', 'to_c'),
    'general_emit': ('pyboxed2.py', 'build'),
    'build': ('pyc.py', 'build'),
    'build_cached': ('pyc.py', 'build_cached'),
    'build_unshadowed_inner': ('pyc.py', '_build_unshadowed_inner'),
    'cc': ('pyc.py', '_cc'),
    'ast_parse': ('ast.py', 'parse'),
    'cache_frontend_key': ('buildcache.py', 'frontend_key'),
    'cache_get': ('buildcache.py', 'get'),
    'cache_write_output': ('buildcache.py', 'write_output'),
    'cache_pack': ('buildcache.py', 'pack'),
}

SITECUSTOMIZE = '''\
import atexit, json, os, sys
_d = os.environ.get("FE_PROFILE_DIR")
if _d:
    import cProfile
    _p = cProfile.Profile()
    _p.enable()
    def _done():
        _p.disable()
        pid = str(os.getpid())
        try:
            with open(os.path.join(_d, pid + ".json"), "w", encoding="utf8") as f:
                json.dump({"argv": sys.argv, "cwd": os.getcwd()}, f)
            _p.dump_stats(os.path.join(_d, pid + ".prof"))
        except OSError:
            pass
    atexit.register(_done)
'''


def median(values):
    return round(statistics.median(values), 4) if values else None


def programs():
    out = []
    for task in sorted(p.name for p in COMPARE.iterdir() if p.is_dir()):
        main = COMPARE / task / 'main.py'
        typed = COMPARE / task / 'typed.py'
        if main.is_file():
            out.append(dict(name=task, source=main, group='compare-main', path='auto',
                            exact=task in ('chain_relax', 'rail_transfer')))
        if typed.is_file():
            out.append(dict(name=task + '-typed', source=typed, group='compare-typed', path='typed'))
    for name in TCC14:
        if name in ('berth_sim', 'echo_pack'):
            continue
        source = CORPUS / (name + '.py')
        if source.is_file():
            out.append(dict(name=name, source=source, group='tcc-corpus', path='auto'))
    return out


def base_env(cache, tmp, pycache, extra=None):
    env = dict(os.environ)
    env.update({'AIL_CACHE': str(cache), 'TMPDIR': str(tmp), 'AIL_NO_CACHE': '1',
                'AIL_SERVER': '0', 'PYTHONUTF8': '1', 'AIL_QUIET_FALLBACK': '',
                'PYTHONPYCACHEPREFIX': str(pycache)})
    if extra:
        env.update(extra)
    return env


def command(source, output):
    return [sys.executable, str(AIL), 'compile', str(source), '-o', str(output), '--syntax', 'python']


def run_once(source, work, env, output, exact=False):
    if exact:
        env = dict(env, AIL_EXACT_INT='1')
    start = time.perf_counter()
    done = subprocess.run(command(source, output), cwd=work, env=env,
                          capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    return dict(wall=wall, returncode=done.returncode,
                stderr=(done.stderr or '')[-4000:], stdout=(done.stdout or '')[-1000:],
                output=str(output))


def importtime(entry, work, env):
    command = [sys.executable, '-X', 'importtime', str(entry), '--help']
    done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=600)
    total = 0.0
    for line in done.stderr.splitlines():
        match = re.search(r'import time:\s+(\d+)\s*\|\s*(\d+)\s*\|', line)
        if match:
            total += int(match.group(1))
    return total / 1_000_000.0


def parse_profiles(directory):
    stats = {}
    files = []
    for path in pathlib.Path(directory).glob('*.prof'):
        argv = {}
        meta = path.with_suffix('.json')
        try:
            argv = json.loads(meta.read_text(encoding='utf8'))
        except (OSError, ValueError):
            pass
        st = pstats.Stats(str(path))
        st.calc_callees()
        kind = 'other'
        joined = ' '.join(argv.get('argv') or [])
        if 'pyc.py' in joined:
            kind = 'inner'
        elif 'ail_chatgpt.py' in joined:
            kind = 'outer'
        files.append((kind, os.path.basename(path), st.stats))
        bucket = stats.setdefault(kind, {})
        for key, value in st.stats.items():
            cc, nc, tt, ct, callers = value
            old = bucket.get(key)
            if old is None:
                bucket[key] = [cc, nc, tt, ct, {}]
            else:
                old[0] += cc
                old[1] += nc
                old[2] += tt
                old[3] += ct
    return stats, files


def pass_times(stats):
    result = {}
    allstats = {}
    for kind in ('outer', 'inner'):
        for key, value in stats.get(kind, {}).items():
            old = allstats.get(key)
            if old is None:
                allstats[key] = [value[0], value[1], value[2], value[3], {}]
            else:
                old[0] += value[0]
                old[1] += value[1]
                old[2] += value[2]
                old[3] += value[3]
    by_name = {}
    for key, value in allstats.items():
        by_name.setdefault((key[0].split('/')[-1], key[2]), []).append(value)
    for name, (filename, func) in PASS_FUNCS.items():
        rows = by_name.get((filename, func), [])
        result[name] = round(sum(row[2] for row in rows), 4) if rows else 0.0
        result[name + '_cum'] = round(sum(row[3] for row in rows), 4) if rows else 0.0
    return result


def top_self(stats, limit=20):
    """Top self time in Python code (outer driver + pyc child).

    Built-in methods are dropped: the outer process' `select.poll` rows are just
    the wall time spent waiting for the child, not front-end work.
    """
    total = {}
    for kind in ('outer', 'inner'):
        for key, value in stats.get(kind, {}).items():
            path, line, func = key
            if path == '~' or func.startswith('<'):
                continue
            bucket = total.setdefault(key, [0.0, 0, 0])
            bucket[0] += value[2]
            bucket[1] += value[0]
            bucket[2] += value[1]
    rows = [dict(file=short_path(key[0]), line=key[1], function=key[2],
                 self=round(value[0], 4), calls=value[1])
            for key, value in total.items()]
    rows.sort(key=lambda row: row['self'], reverse=True)
    return rows[:limit]


def short_path(path):
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO))
    except (ValueError, OSError):
        return path


def ensure_site(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'sitecustomize.py').write_text(SITECUSTOMIZE, encoding='utf8')
    return directory


def profile_build(source, work, pycache, profile_dir, exact=False):
    ensure_site(profile_dir)
    cache, tmp = work / 'cache', work / 'tmp'
    cache.mkdir(); tmp.mkdir()
    env = base_env(cache, tmp, pycache, {'FE_PROFILE_DIR': str(profile_dir),
                                         'PYTHONPATH': str(profile_dir)})
    result = run_once(source, work, env, work / 'prog-prof', exact=exact)
    stats, _ = parse_profiles(profile_dir)
    passes = pass_times(stats)
    return dict(wall=result['wall'], returncode=result['returncode'],
                stderr=result['stderr'], passes=passes,
                top_self=top_self(stats))


def timed_build(source, work, pycache, cache=None, tmp=None, tag='cold', exact=False):
    """Run the CLI through timed_outer.py; return low-overhead pass timings."""
    work.mkdir(parents=True, exist_ok=True)
    cache = cache or (work / 'cache')
    tmp = tmp or (work / 'tmp')
    cache.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    outer_out = work / ('outer-%s.json' % tag)
    inner_out = work / ('inner-%s.json' % tag)
    env = base_env(cache, tmp, pycache, {'FE_TIME_OUT_OUTER': str(outer_out),
                                         'FE_TIME_OUT_INNER': str(inner_out)})
    if cache is not None and tag == 'warm':
        env['AIL_NO_CACHE'] = ''
    command = [sys.executable, str(TIMED_OUTER), 'compile', str(source),
               '-o', str(work / ('prog-timed-%s' % tag)), '--syntax', 'python']
    if exact:
        env = dict(env, AIL_EXACT_INT='1')
    start = time.perf_counter()
    done = subprocess.run(command, cwd=str(work), env=env, capture_output=True,
                          text=True, timeout=1800)
    wall = time.perf_counter() - start
    outer = inner = None
    try:
        outer = json.loads(outer_out.read_text(encoding='utf8'))
    except (OSError, ValueError):
        pass
    try:
        inner = json.loads(inner_out.read_text(encoding='utf8'))
    except (OSError, ValueError):
        pass
    return dict(wall=wall, returncode=done.returncode, stderr=done.stderr[-3000:],
                outer=outer, inner=inner)


def phases(source, timed):
    """Non-overlapping cold-build phases from the timed wrapper (seconds)."""
    outer = timed.get('outer') or {}
    inner = timed.get('inner') or {}
    otimers = outer.get('timers') or {}
    itimers = inner.get('timers') or {}

    def total(bucket, label):
        return (bucket.get(label) or {}).get('total', 0.0)

    def exclusive(bucket, label):
        return (bucket.get(label) or {}).get('exclusive', 0.0)

    startup = outer.get('import', 0.0) + inner.get('import', 0.0)
    load = total(otimers, 'load_sources')
    passes = sum(exclusive(itimers, label) for label in
                 ('fold_int_constants', 'refuse_static_big_calls',
                  'python_defs_only_runs_nothing', 'refuse_big_capable',
                  'refuse_typed_big_store'))
    typed = exclusive(itimers, 'typed_emit')
    general = exclusive(itimers, 'general_emit')
    cc = exclusive(itimers, 'cc')
    other = max(0.0, timed['wall'] - startup - load - passes - typed - general - cc)
    return dict(startup_imports=round(startup, 4),
                outer_load=round(load, 4),
                inner_pre_passes=round(passes, 4),
                typed_emit=round(typed, 4),
                general_emit=round(general, 4),
                c_compile_link=round(cc, 4),
                other=round(other, 4),
                total=round(timed['wall'], 4),
                typed_attempt=round(total(itimers, 'typed_emit'), 4),
                general_attempt=round(total(itimers, 'general_emit'), 4))


def memory_run(source, work, pycache, exact=False):
    cache, tmp = work / 'cache', work / 'tmp'
    cache.mkdir(parents=True, exist_ok=True); tmp.mkdir(parents=True, exist_ok=True)
    env = base_env(cache, tmp, pycache)
    if exact:
        env = dict(env, AIL_EXACT_INT='1')
    start = time.perf_counter()
    done = subprocess.run(['/usr/bin/time', '-v', *command(source, work / 'prog-mem')],
                          cwd=work, env=env, capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    peak = None
    match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', done.stderr)
    if match:
        peak = int(match.group(1))
    return dict(wall=wall, returncode=done.returncode, peak_kb=peak,
                stderr=done.stderr[-2000:])


def warm_run(source, work, pycache, reps=3, exact=False):
    cache, tmp = work / 'cache', work / 'tmp'
    cache.mkdir(parents=True, exist_ok=True); tmp.mkdir(parents=True, exist_ok=True)
    env = base_env(cache, tmp, pycache, {'AIL_NO_CACHE': ''})
    if exact:
        env = dict(env, AIL_EXACT_INT='1')
    first = run_once(source, work, env, work / 'prog-warm0')
    if first['returncode'] != 0:
        return dict(fill=first, walls=[], peak_kb=None)
    walls = []
    for i in range(reps):
        result = run_once(source, work, env, work / ('prog-warm%d' % (i + 1)))
        if result['returncode'] != 0:
            return dict(fill=first, walls=walls, error=result['stderr'])
        walls.append(result['wall'])
    prof_dir = ensure_site(work / 'profile-warm')
    penv = dict(env, FE_PROFILE_DIR=str(prof_dir), PYTHONPATH=str(prof_dir))
    prof = run_once(source, work, penv, work / 'prog-warm-prof')
    stats, _ = parse_profiles(prof_dir)
    timed = timed_build(source, work / 'timed-warm', pycache, cache=cache, tmp=tmp, tag='warm', exact=exact)
    return dict(fill_wall=first['wall'], walls=walls, median=median(walls),
                passes=pass_times(stats), profile_wall=prof['wall'],
                timed=timed, phases=phases(source, timed))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path, default=HERE / 'results.json')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--only', action='append', help='program name substring; repeatable')
    ap.add_argument('--skip-profile', action='store_true')
    ap.add_argument('--skip-memory', action='store_true')
    ap.add_argument('--skip-warm', action='store_true')
    ap.add_argument('--work', type=pathlib.Path, help='keep everything here instead of /tmp')
    args = ap.parse_args(argv)

    rows = programs()
    if args.only:
        rows = [row for row in rows if any(part in row['name'] for part in args.only)]
    root = args.work or pathlib.Path(tempfile.mkdtemp(prefix='ail-fe-'))
    root.mkdir(parents=True, exist_ok=True)
    pycache = root / 'pycache'
    report = dict(schema='ail.fe/1', date=time.strftime('%Y-%m-%d'),
                  python=sys.version.split()[0], platform=platform.platform(),
                  reps=args.reps, tcc14=list(TCC14), programs=[])

    # Import costs are measured once; they do not depend on the source.
    probe = root / 'probe'
    cache, tmp = probe / 'cache', probe / 'tmp'
    cache.mkdir(parents=True); tmp.mkdir(parents=True)
    env = base_env(cache, tmp, pycache)
    report['importtime_outer'] = round(median([importtime(AIL, probe, env) for _ in range(3)]), 4)
    report['importtime_inner'] = round(median([importtime(PYC, probe, env) for _ in range(3)]), 4)

    for index, row in enumerate(rows, 1):
        source = row['source']
        name = row['name']
        work = root / ('p%02d-%s' % (index, re.sub(r'[^A-Za-z0-9_.-]', '_', name)))
        work.mkdir(parents=True, exist_ok=True)
        cache, tmp = work / 'cache', work / 'tmp'
        cache.mkdir(); tmp.mkdir()
        env = base_env(cache, tmp, pycache)
        walls, errors = [], []
        path_kind = []
        for rep in range(args.reps):
            # A fresh cache directory for every repetition: a genuinely cold build.
            cache_rep = work / ('cache%d' % rep)
            tmp_rep = work / ('tmp%d' % rep)
            cache_rep.mkdir(); tmp_rep.mkdir()
            renv = base_env(cache_rep, tmp_rep, pycache)
            result = run_once(source, work, renv, work / ('prog%d' % rep), exact=row.get('exact', False))
            walls.append(result['wall'])
            if result['returncode'] != 0:
                errors.append(result['stderr'])
                break
            note = 'built on the general path' in result['stderr']
            path_kind.append('general' if note else 'typed')
        entry = dict(name=name, group=row['group'], source=short_path(str(source)),
                     cold_walls=[round(w, 4) for w in walls], cold_median=median(walls),
                     returncode=0 if not errors else 1, path=path_kind[0] if path_kind else 'error')
        if errors:
            entry['error'] = errors[0]
        print('[%02d/%02d] %-24s %s %.3fs %s' % (index, len(rows), name,
              'ERR' if errors else entry['path'], entry['cold_median'] or 0,
              ' '.join('%.2f' % w for w in walls)), flush=True)
        if not errors:
            if not args.skip_memory:
                mem = memory_run(source, work / 'mem', pycache, exact=row.get('exact', False))
                entry['peak_kb'] = mem['peak_kb']
                entry['memory_wall'] = round(mem['wall'], 4)
            if not args.skip_profile:
                prof = profile_build(source, work / 'profile', pycache, work / 'profile' / 'stats', exact=row.get('exact', False))
                entry['profile_wall'] = round(prof['wall'], 4)
                entry['passes'] = prof['passes']
                entry['top_self'] = prof['top_self']
                timed = timed_build(source, work / 'timed', pycache, exact=row.get('exact', False))
                entry['timed'] = timed
                entry['phases'] = phases(source, timed)
            if not args.skip_warm:
                warm = warm_run(source, work / 'warm', pycache, args.reps, exact=row.get('exact', False))
                entry['warm'] = warm
        report['programs'].append(entry)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=False), encoding='utf8')

    # Aggregate top-20 self time over every profiled program.
    combined = {}
    for entry in report['programs']:
        for row in entry.get('top_self') or []:
            key = (row['file'], row['line'], row['function'])
            old = combined.setdefault(key, [0.0, 0])
            old[0] += row['self']
            old[1] += row['calls']
    top = [dict(file=key[0], line=key[1], function=key[2], self=round(value[0], 4),
                calls=value[1]) for key, value in combined.items()]
    top.sort(key=lambda row: row['self'], reverse=True)
    report['top20_self'] = top[:20]
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False), encoding='utf8')
    print('wrote', args.out)
    if not args.work:
        print('work dir', root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
