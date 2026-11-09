#!/usr/bin/env python3
"""Measure two real pure-Python libraries against AIL's CPython hybrid and native rewrites.

    python3 lab/wedge3/wedge3d/harness.py [--only dateutil,ahocorapy] [-o results.json]

For each library this script:
  * times CPython and PyPy 3.10 on the pure library (median of 5),
  * copies the package into a temp dir, builds `ail build --cpython` for the hot module,
    moves the extension out of the package directory, and times the hybrid,
  * records run-time kinds with `ail_observe.py run --fast`, annotates the hot module with
    `--strip`, rebuilds, and times the observed-kind hybrid,
  * times the native library (ciso8601 for dateutil, ahocorasick_rs for ahocorapy),
  * checks every run's stdout byte for byte against CPython,
  * profiles CPython and ranks the build's refusal reasons by the self time they cost.

Nothing outside lab/wedge3/wedge3d is modified.  The hybrid AIL tree is the job-obs5-op1109
worktree (default ../obs5), not this checkout's AIL_CURRENT.
"""
import argparse
import ast
import concurrent.futures
import json
import os
import pstats
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_AIL = ROOT.parent / 'obs5' / 'AIL_CURRENT'
PY = os.environ.get('W3D_PYTHON', '/tmp/w3d-venv/bin/python')
PYPY = os.environ.get('W3D_PYPY', '/opt/hostedtoolcache/PyPy/3.10.16/x64/bin/pypy3')
REPS = 5
TIME_LIMIT = 900

LIBS = {
    'dateutil': {
        'package': 'dateutil',
        'hot': 'dateutil/parser/_parser.py',
        'driver': 'date_parse.py',
        'small': {'W3D_N': '2000'},
        'big': {'W3D_N': '50000'},
        'native': 'ciso8601 (C)',
    },
    'ahocorapy': {
        'package': 'ahocorapy',
        'hot': 'ahocorapy/keywordtree.py',
        'driver': 'aho_search.py',
        'small': {'W3D_REPEATS': '5000'},
        'big': {'W3D_REPEATS': '100000'},
        'native': 'ahocorasick_rs (Rust)',
    },
}


def log(msg):
    print(msg, flush=True)


def package_dir(python, name):
    code = 'import %s, os; print(os.path.dirname(%s.__file__))' % (name, name)
    return Path(subprocess.run([python, '-c', code], capture_output=True, text=True,
                               check=True).stdout.strip())


def copy_package(src, dest):
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def base_env(extra=None):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith('AIL_') or k == 'PYTHONPATH':
            del env[k]
    env['AIL_NO_CACHE'] = '1'
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


def one_run(cmd, cwd, env, expected=None, timeout=TIME_LIMIT):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, timeout=timeout)
    dt = time.perf_counter() - t0
    if p.returncode != 0:
        raise RuntimeError('%s failed (%d): %s' % (' '.join(map(str, cmd)), p.returncode,
                                                   p.stderr.decode('utf-8', 'replace')[-1200:]))
    out = p.stdout
    if expected is not None and out != expected:
        raise RuntimeError('output mismatch for %s\nCPython: %r\nother:   %r'
                           % (' '.join(map(str, cmd)), expected[:800], out[:800]))
    return dt, out


def median5(cmd, cwd, env, expected, timeout=TIME_LIMIT):
    times = []
    for _ in range(REPS):
        dt, out = one_run(cmd, cwd, env, expected, timeout)
        times.append(dt)
    return {'median_s': statistics.median(times), 'times_s': [round(t, 6) for t in times]}


def build(ail, source, out, cwd):
    if out.exists():
        shutil.rmtree(out)
    p = subprocess.run([PY, '-B', str(ail / 'ail_chatgpt.py'), 'build', '--cpython',
                        str(source), '-o', str(out)], cwd=str(cwd), env=base_env(),
                       capture_output=True, text=True, timeout=TIME_LIMIT)
    if p.returncode != 0:
        raise RuntimeError('hybrid build failed: %s' % (p.stderr or p.stdout)[-2000:])
    return json.loads((out / 'build.json').read_text())


def install_hybrid(out, pkgroot, hot_rel):
    native = pkgroot / 'native'
    native.mkdir(parents=True, exist_ok=True)
    sos = list(out.glob('*.so'))
    for so in sos:
        shutil.copy2(so, native / so.name)
    hot = pkgroot / hot_rel
    run_file = out / (hot.stem + '_run.py')
    shutil.copy2(run_file, hot)
    return [s.name for s in sos]


def run_env(pkgroot):
    return {'PYTHONPATH': str(pkgroot / 'native') + os.pathsep + str(pkgroot)}


def count_functions(hot_path):
    tree = ast.parse(hot_path.read_text(encoding='utf-8'))
    top = 0
    methods = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top += 1
        elif isinstance(node, ast.ClassDef):
            methods += sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                           for n in node.body)
    defs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {'top_level': top, 'methods': methods, 'defs': len(defs)}


def qualname_map(hot_path):
    """name -> qualname, and (name, lineno) -> qualname, for AST defs in the hot module."""
    tree = ast.parse(hot_path.read_text(encoding='utf-8'))
    by_name = {}
    by_line = {}
    stack = []

    def visit(node, prefix):
        for child in getattr(node, 'body', []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = (prefix + '.' if prefix else '') + child.name
                by_name.setdefault(child.name, set()).add(qual)
                by_line[(child.name, child.lineno)] = qual
                for d in child.decorator_list:
                    by_line[(child.name, d.lineno)] = qual
            elif isinstance(child, ast.ClassDef):
                visit(child, (prefix + '.' if prefix else '') + child.name)
    visit(tree, '')
    return by_name, by_line


def normalise_reason(text):
    text = text or ''
    for tail in (', stays in CPython', ' stays in CPython'):
        if text.endswith(tail):
            text = text[:-len(tail)]
    return text


def refusal_ranking(profile_path, hot_path, report):
    stats = pstats.Stats(str(profile_path))
    by_name, by_line = qualname_map(hot_path)
    hot_name = hot_path.name
    rejected = {k: normalise_reason(v) for k, v in (report.get('rejected') or {}).items()}
    accelerated = set(report.get('accelerated') or [])
    per_qual = {}
    for (fn, line, name), (_cc, _nc, tt, _ct, _callers) in stats.stats.items():
        if Path(fn).name != hot_name:
            continue
        qual = by_line.get((name, line))
        if qual is None:
            candidates = by_name.get(name) or set()
            if len(candidates) == 1:
                qual = next(iter(candidates))
            else:
                qual = name
        per_qual[qual] = per_qual.get(qual, 0.0) + tt
    reasons = {}
    native_s = 0.0
    for qual, total in per_qual.items():
        if qual in accelerated:
            native_s += total
            continue
        key = qual if qual in rejected else qual
        reason = rejected.get(key)
        if reason is None:
            reason = 'no refusal recorded (not selected as a candidate)'
        row = reasons.setdefault(reason, {'reason': reason, 'self_s': 0.0, 'functions': []})
        row['self_s'] += total
        row['functions'].append(qual)
    rows = sorted(reasons.values(), key=lambda r: r['self_s'], reverse=True)
    for row in rows:
        row['self_s'] = round(row['self_s'], 6)
        row['functions'].sort()
    total_s = sum(per_qual.values())
    return {'hot_self_s': round(total_s, 6), 'native_self_s': round(native_s, 6),
            'reasons': rows}


def measure_library(name, cfg, ail, work, only_steps):
    log('== %s ==' % name)
    pkg_src = package_dir(PY, cfg['package'])
    driver_src = HERE / 'workloads' / cfg['driver']
    big = cfg['big']
    small = cfg['small']
    work = work / name
    work.mkdir(parents=True, exist_ok=True)

    base = work / 'base'
    base.mkdir(exist_ok=True)
    shutil.copy2(driver_src, base / 'driver.py')
    _, expected = one_run([PY, 'driver.py'], base, base_env(big))
    log('CPython output: %s' % expected.decode('utf-8', 'replace').strip())

    rec = {'library': name, 'package': cfg['package'], 'hot_module': cfg['hot'],
           'native_rewrite': cfg['native'], 'workload': cfg['driver'],
           'driver_env': big, 'output': expected.decode('utf-8', 'replace').strip()}

    if 'cpython' in only_steps:
        rec['cpython'] = median5([PY, 'driver.py'], base, base_env(big), expected)
        log('CPython      %.4f s' % rec['cpython']['median_s'])

    if 'pypy' in only_steps:
        pypy_base = work / 'pypy'
        pypy_base.mkdir(exist_ok=True)
        shutil.copy2(driver_src, pypy_base / 'driver.py')
        rec['pypy'] = median5([PYPY, 'driver.py'], pypy_base, base_env(big), expected)
        rec['pypy_version'] = subprocess.run([PYPY, '--version'], capture_output=True,
                                             text=True).stdout.splitlines()[0]
        log('PyPy         %.4f s' % rec['pypy']['median_s'])

    if 'native' in only_steps:
        rec['native'] = median5([PY, 'driver.py'], base, base_env(dict(big, W3D_IMPL='native')),
                                expected)
        log('native       %.4f s' % rec['native']['median_s'])

    plain_root = work / 'plain'
    copy_package(pkg_src, plain_root / cfg['package'])
    shutil.copy2(driver_src, plain_root / 'driver.py')
    if 'hybrid' in only_steps:
        out = work / 'build_plain'
        report = build(ail, plain_root / cfg['hot'], out, plain_root)
        rec['hybrid_report'] = report
        install_hybrid(out, plain_root, cfg['hot'])
        rec['hybrid'] = median5([PY, 'driver.py'], plain_root, base_env(dict(big, **run_env(plain_root))),
                                expected)
        rec['functions'] = count_functions(plain_root / cfg['hot'])
        rec['functions']['native_plain'] = len(report.get('accelerated') or [])
        log('hybrid plain %.4f s native=%d/%d' % (rec['hybrid']['median_s'],
                                                  rec['functions']['native_plain'],
                                                  rec['functions']['defs']))

    obs_root = work / 'obs'
    copy_package(pkg_src, obs_root / cfg['package'])
    shutil.copy2(driver_src, obs_root / 'driver.py')
    if 'observed' in only_steps:
        profile = work / 'observe.json'
        p = subprocess.run([PY, '-B', str(ail / 'ail_observe.py'), 'run', '--fast',
                            '-o', str(profile), 'driver.py'], cwd=str(obs_root),
                           env=base_env(dict(small, **run_env(obs_root))),
                           capture_output=True, text=True, timeout=TIME_LIMIT)
        if p.returncode != 0:
            raise RuntimeError('recorder failed: %s' % (p.stderr or p.stdout)[-2000:])
        hot = obs_root / cfg['hot']
        p = subprocess.run([PY, '-B', str(ail / 'ail_observe.py'), 'annotate', str(profile),
                            str(hot), '--strip', '-o', str(hot)], cwd=str(obs_root),
                           env=base_env(), capture_output=True, text=True, timeout=TIME_LIMIT)
        if p.returncode != 0:
            raise RuntimeError('annotate failed: %s' % (p.stderr or p.stdout)[-2000:])
        _, annotated_out = one_run([PY, 'driver.py'], obs_root,
                                   base_env(dict(big, **run_env(obs_root))))
        rec['annotated_output_matches'] = annotated_out == expected
        out = work / 'build_obs'
        report = build(ail, hot, out, obs_root)
        rec['observed_report'] = report
        install_hybrid(out, obs_root, cfg['hot'])
        rec['observed'] = median5([PY, 'driver.py'], obs_root,
                                  base_env(dict(big, **run_env(obs_root))), expected)
        rec['functions_observed'] = count_functions(obs_root / cfg['hot'])
        rec['functions_observed']['native_observed'] = len(report.get('accelerated') or [])
        log('hybrid obs   %.4f s native=%d/%d' % (rec['observed']['median_s'],
                                                  rec['functions_observed']['native_observed'],
                                                  rec['functions_observed']['defs']))

        # refusal ranking from the observed build (same selection as plain here)
        prof = work / 'cprofile.out'
        p = subprocess.run([PY, '-m', 'cProfile', '-o', str(prof), 'driver.py'], cwd=str(base),
                           env=base_env(big), capture_output=True, text=True, timeout=TIME_LIMIT)
        if p.returncode == 0 and prof.is_file():
            hot_original = pkg_src / Path(cfg['hot']).relative_to(cfg['package'])
            rec['refusals'] = refusal_ranking(prof, hot_original, report)
            log('refusals: ' + '; '.join('%s (%.3fs)' % (r['reason'][:52], r['self_s'])
                                         for r in rec['refusals']['reasons'][:4]))

    def ratio(a, b):
        if a and b and a.get('median_s') and b.get('median_s'):
            return round(a['median_s'] / b['median_s'], 3)
        return None
    for label in ('hybrid', 'observed'):
        rec[label + '_ratio_cpython'] = ratio(rec.get(label), rec.get('cpython'))
        rec[label + '_ratio_pypy'] = ratio(rec.get(label), rec.get('pypy'))
        rec[label + '_ratio_native'] = ratio(rec.get(label), rec.get('native'))
        rec['native_ratio_cpython'] = ratio(rec.get('native'), rec.get('cpython'))
    return rec


def sanitize(value, work, ail):
    """Replace machine-specific temp/AIL prefixes in the committed JSON."""
    if isinstance(value, dict):
        return {k: sanitize(v, work, ail) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, work, ail) for v in value]
    if isinstance(value, str):
        return value.replace(str(work), '<work>').replace(str(ail), '../obs5/AIL_CURRENT')
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only')
    ap.add_argument('--steps', default='cpython,pypy,native,hybrid,observed',
                    help='comma-separated subset to re-run')
    ap.add_argument('--ail', default=os.environ.get('W3D_AIL', str(DEFAULT_AIL)))
    ap.add_argument('-o', '--out', default=str(HERE / 'results.json'))
    args = ap.parse_args()
    ail = Path(args.ail).resolve()
    names = [n for n in LIBS if not args.only or n in args.only.split(',')]
    steps = set(args.steps.split(','))
    work = Path(tempfile.mkdtemp(prefix='w3d-'))
    log('AIL %s' % ail)
    log('work %s' % work)
    results = {'schema': 'ail.wedge3d/1', 'ail': str(ail),
               'ail_commit': subprocess.run(['git', '-C', str(ail.parent), 'rev-parse', 'HEAD'],
                                            capture_output=True, text=True).stdout.strip(),
               'python': subprocess.run([PY, '--version'], capture_output=True,
                                        text=True).stdout.strip(),
               'pypy': PYPY, 'libraries': []}
    for name in names:
        try:
            results['libraries'].append(measure_library(name, LIBS[name], ail, work, steps))
        except Exception as error:
            log('%s FAILED: %s' % (name, error))
            results['libraries'].append({'library': name, 'error': '%s: %s'
                                         % (type(error).__name__, error)})
        Path(args.out).write_text(json.dumps(sanitize(results, work, ail), indent=2,
                                                 sort_keys=True) + '\n')
        log('wrote %s' % args.out)


if __name__ == '__main__':
    main()
