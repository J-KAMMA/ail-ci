#!/usr/bin/env python3
"""wedge3c: two real libraries, pure Python vs the CPython hybrid vs the native rewrite.

    /tmp/wedge3venv/bin/python lab/wedge3/wedge3c/bench.py [-o results.json]

The libraries are pip-installed, never vendored: the harness copies the installed packages into a
temporary directory at run time.  The hot module is made a valid AIL entry file for the build
(jellyfish 0.8.9 calls `unicodedata.normalize`, which the emitter refuses; msgpack's `fallback.py`
uses package-relative imports).  Nothing in the timed package is changed: with zero functions
selected the hybrid is the unmodified library, and the build reports say so.

Times are the median of 5 runs under `ulimit -v 2500000`, one workload at a time.  Stdout and the
exit status are compared byte for byte with CPython for every column.
"""
import argparse
import ast
import hashlib
import json
import os
import pstats
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKLOADS = HERE / 'workloads'
REPS = 5


def limited(cmd):
    """Every measured process runs under the 2.5 GB address-space limit."""
    return ['bash', '-c', 'ulimit -v 2500000; exec "$@"', '_'] + [str(c) for c in cmd]


def _env(**extra):
    env = dict(os.environ)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.update({k: v for k, v in extra.items() if v is not None})
    return env


def run(cmd, cwd, env, timeout=900, check=False, limit=True):
    p = subprocess.run(limited(cmd) if limit else [str(c) for c in cmd],
                       cwd=str(cwd), env=env, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError('%s failed: %s' % (' '.join(map(str, cmd)),
                                              p.stderr.decode('utf-8', 'replace')[-2000:]))
    return p


def timed(cmd, cwd, env, reps=REPS):
    """Median wall time, and the first result; every rep must agree byte for byte."""
    times, first = [], None
    for _ in range(reps):
        t0 = time.perf_counter()
        p = run(cmd, cwd, env)
        times.append(time.perf_counter() - t0)
        if first is None:
            first = p
        elif (p.returncode, p.stdout) != (first.returncode, first.stdout):
            raise RuntimeError('non-deterministic output for %s' % (cmd,))
    return statistics.median(times), first


def copy_package(venv_site, package, dest):
    """Copy only the Python sources of an installed package (never its .so)."""
    src = Path(venv_site) / package
    dst = Path(dest) / package
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and (f.suffix in ('.py', '.pyi') or f.name == 'py.typed'):
            shutil.copy2(f, dst / f.name)
    return dst


def count_functions(text, include_methods=False):
    """The hybrid's units: module-level defs, plus direct class methods when asked."""
    tree = ast.parse(text)
    count = sum(1 for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    if include_methods:
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                count += sum(1 for m in node.body
                             if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return count


def prepare_jellyfish(text):
    """The hot module as an AIL entry file.

    Two constructs stop the entry build before the mixed-mode analysis can slice anything:
    `unicodedata.normalize` (not in the subset) and the package-relative `from .porter import`.
    Both belong to `_normalize`/`porter_stem`, which are not the measured functions (and cannot be
    candidates anyway: `unicodedata` and `porter.Stemmer` are unsupported).  Remove the imports and
    neutralise `_normalize` so the rest of the module reaches the analysis.  `_normalize` is left
    returning its argument: it is refused (`to_c-refused`) and nothing is deployed, so the timed
    library keeps its original code.
    """
    text = re.sub(r'^import unicodedata\r?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^from \.porter import Stemmer\r?\n', '', text, flags=re.MULTILINE)
    return text.replace('    return unicodedata.normalize("NFKD", s)', '    return s')


def prepare_msgpack(text):
    """Package-relative imports become absolute; the copied package is on PYTHONPATH."""
    return (text.replace('from .exceptions import', 'from msgpack.exceptions import')
                .replace('from .ext import', 'from msgpack.ext import'))


PREPARE = {'jellyfish': prepare_jellyfish, 'msgpack': prepare_msgpack}

# The functions the jellyfish workload calls, plus the two helpers in their call graph.  The rest
# of the module is never executed (0 s), and one of the untouched helpers (`damerau...`, a
# `defaultdict`) stops the unannotated entry build before the analysis can slice anything.
JELLYFISH_SLICE = {'_normalize', '_check_type', 'levenshtein_distance', '_jaro_winkler',
                   'jaro_winkler_similarity', 'soundex'}
# `_normalize` is the one body `prepare_jellyfish` had to neutralise.  The build may select it;
# it is not a native rewrite of the real function and the harness never deploys it.
UNSOUND = {'jellyfish': {'_normalize'}, 'msgpack': set()}


def slice_functions(text, names):
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    return ''.join(''.join(lines[n.lineno - 1:n.end_lineno]) + '\n'
                   for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names)


def build_hybrid(text, name, work, ail, py):
    """`ailc ext` (build --cpython) on one prepared module, returning its build.json."""
    src_dir = Path(tempfile.mkdtemp(prefix='hybrid-src-', dir=str(work)))
    src = src_dir / (name + '.py')
    src.write_text(text, encoding='utf-8')
    out = src_dir / 'out'
    p = run([py, str(ail / 'ail_chatgpt.py'), 'build', '--cpython', str(src), '-o', str(out)],
            src_dir, _env(AIL_NO_CACHE='1'), check=False)
    report_path = out / 'build.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {
        'accelerated': [], 'rejected': {},
        'error': p.stderr.decode('utf-8', 'replace')[-2000:]}
    shutil.rmtree(src_dir, ignore_errors=True)
    return report


def observe_docs(py, ail, pkg_root, package, hot, workload):
    """Record the workload, then annotate a copy of the hot module with the observed kinds."""
    src = pkg_root / package / hot
    local = pkg_root / 'work.py'
    shutil.copy2(workload, local)
    prof = pkg_root / 'observe.json'
    env = _env(PYTHONPATH=str(pkg_root))
    if package == 'msgpack':
        env['MSGPACK_PUREPYTHON'] = '1'
    run([py, str(ail / 'ail_observe.py'), 'run', '-o', str(prof), str(local)],
        pkg_root, env, timeout=900, check=True)
    annotated = pkg_root / package / ('observed_' + hot)
    run([py, str(ail / 'ail_observe.py'), 'annotate', str(prof), str(src), '-o', str(annotated),
         '--decisions', str(pkg_root / 'decisions.json')], pkg_root, env, check=True)
    return annotated.read_text(encoding='utf-8')


def qualname_by_line(text):
    """{(name, def_lineno): qualname} so a cProfile row maps to a build.json key."""
    out = {}

    def walk(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[(node.name, node.lineno)] = prefix + node.name
            elif isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + '.')

    walk(ast.parse(text).body, '')
    return out


def profile(py, workload, cwd, env, hot_file, module_text):
    out = Path(tempfile.mkstemp(prefix='profile-', suffix='.out')[1])
    code = ('import cProfile, pstats, runpy, sys\n'
            'cProfile.runctx("runpy.run_path(%r, run_name=\\"__main__\\")",\n'
            ' globals(), {"runpy": runpy}, %r)\n' % (str(workload), str(out)))
    run([py, '-B', '-c', code], cwd, env, check=True)
    stats = pstats.Stats(str(out))
    names = qualname_by_line(module_text)
    rows = {}
    for (fn, line, name), (cc, nc, tt, ct, _callers) in stats.stats.items():
        if Path(fn).name == hot_file:
            key = names.get((name, line), name)
            rows[key] = {'calls': nc, 'self_s': round(tt, 6), 'cum_s': round(ct, 6)}
    try:
        out.unlink()
    except OSError:
        pass
    return rows


def icount_binary():
    """tools/icount.c, built once; None when the runner forbids perf_event_open."""
    exe = Path('/tmp/wedge3c-icount')
    if not exe.exists():
        src = Path(__file__).resolve().parents[3] / 'tools' / 'icount.c'
        cc = subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h',
                             '-o', str(exe), str(src)], capture_output=True)
        if cc.returncode != 0:
            return None
    probe = subprocess.run([str(exe), sys.executable, '-c', 'pass'], capture_output=True)
    return exe if probe.returncode == 0 else None


def reason_of(report, func):
    if func in (report.get('accelerated') or []):
        return 'selected by the build'
    return (report.get('rejected') or {}).get(func) or 'not reported by the build'


def rank_reasons(prof, report):
    reasons = {}
    for func, row in prof.items():
        if func == '<module>':
            continue
        why = reason_of(report, func)
        entry = reasons.setdefault(why, {'self_s': 0.0, 'functions': [], 'calls': 0})
        entry['self_s'] = round(entry['self_s'] + row['self_s'], 6)
        entry['functions'].append(func)
        entry['calls'] += row['calls']
    return sorted(({'reason': k, 'self_s': v['self_s'], 'calls': v['calls'],
                    'functions': sorted(v['functions'])} for k, v in reasons.items()),
                  key=lambda item: -item['self_s'])


def bench_library(name, package, hot, workload, pure_site, native_py, native_site,
                  pypy, ail, work, icount):
    pure = work / ('pure_' + name)
    pure.mkdir(parents=True)
    copy_package(pure_site, package, pure)
    original = (pure / package / hot).read_text(encoding='utf-8')
    if package == 'jellyfish':
        for f in (pure / package).glob('*cjellyfish*'):
            f.unlink()

    env_pure = _env(PYTHONPATH=str(pure))
    env_native = _env(PYTHONPATH=str(native_site) if native_site else None)
    if package == 'msgpack':
        env_pure['MSGPACK_PUREPYTHON'] = '1'

    # Hybrid, without and with observed kinds.  Both are built from the prepared module; with
    # zero selected functions the harness times the untouched pure library (the build is a no-op).
    if name == 'jellyfish':
        plain_source = slice_functions(prepare_jellyfish(original), JELLYFISH_SLICE)
    else:
        plain_source = PREPARE[name](original)
    plain_report = build_hybrid(plain_source, hot[:-3], work, ail, sys.executable)
    obs_root = work / ('observed_' + name)
    obs_root.mkdir()
    copy_package(pure_site, package, obs_root)
    if package == 'jellyfish':
        for f in (obs_root / package).glob('*cjellyfish*'):
            f.unlink()
    observed_text = observe_docs(sys.executable, ail, obs_root, package, hot, workload)
    if name == 'jellyfish':
        observed_source = slice_functions(prepare_jellyfish(observed_text), JELLYFISH_SLICE)
    else:
        observed_source = PREPARE[name](observed_text)
    observed_report = build_hybrid(observed_source, hot[:-3], work, ail, sys.executable)

    # Deployment would bind each accelerated function back onto the original module.  No real
    # function is selected; `_normalize` is the sanitised helper and is only reported.
    for tag, report in (('hybrid', plain_report), ('hybrid_obs', observed_report)):
        real = [f for f in (report.get('accelerated') or []) if f not in UNSOUND[name]]
        if real:
            raise SystemExit('%s: unexpected selected functions %r' % (tag, real))

    configs = [
        ('cpython', [sys.executable, str(workload)], env_pure),
        ('pypy', [str(pypy), str(workload)], env_pure),
        ('hybrid', [sys.executable, str(workload)], env_pure),
        ('hybrid_obs', [sys.executable, str(workload)], env_pure),
        ('native', [str(native_py), str(workload)], env_native),
    ]
    base = None
    result = {
        'library': name, 'package': package, 'hot_module': hot,
        'functions_total': count_functions(original, include_methods=(package == 'msgpack')),
        'functions_top_level': count_functions(original),
        'native_functions': len([f for f in (plain_report.get('accelerated') or [])
                                 if f not in UNSOUND[name]]),
        'selected_helpers': [f for f in (plain_report.get('accelerated') or [])
                             if f in UNSOUND[name]],
        'selected_helpers_observed': [f for f in (observed_report.get('accelerated') or [])
                                      if f in UNSOUND[name]],
        'build_plain': plain_report, 'build_observed': observed_report,
        'times': {}, 'instructions': {}, 'match': {}, 'output_sha': {},
    }
    for key, cmd, env in configs:
        secs, p = timed(cmd, work, env)
        result['times'][key] = round(secs, 6)
        result['output_sha'][key] = hashlib.sha256(p.stdout).hexdigest()
        if base is None:
            base = p
            result['cpython_stdout'] = p.stdout.decode('utf-8', 'replace')
        result['match'][key] = (p.returncode == base.returncode and p.stdout == base.stdout)
        if icount is not None:
            ic = subprocess.run(limited([str(icount)] + cmd), cwd=str(work), env=env,
                                capture_output=True)
            result['instructions'][key] = (int(ic.stdout) if ic.returncode == 0 and
                                           ic.stdout.strip().isdigit() else None)

    result['profile'] = profile(sys.executable, workload, work, env_pure, hot, original)
    result['refusals'] = rank_reasons(result['profile'], plain_report)
    result['observed_refusals'] = rank_reasons(result['profile'], observed_report)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=str(HERE / 'results.json'))
    ap.add_argument('--cpy', default='/tmp/wedge3venv/bin/python')
    ap.add_argument('--cpy-site', default='/tmp/wedge3venv/lib/python3.12/site-packages')
    ap.add_argument('--native', default='/tmp/wedge3native/bin/python')
    ap.add_argument('--native-site', default='/tmp/wedge3native/lib/python3.12/site-packages')
    ap.add_argument('--pypy', default='/tmp/pypy/pypy3.10-v7.3.17-linux64/bin/pypy3')
    ap.add_argument('--ail', default='/home/runner/work/_temp/obs5/AIL_CURRENT')
    a = ap.parse_args()
    # This process must be the CPython venv interpreter (the build uses it).
    work = Path(tempfile.mkdtemp(prefix='wedge3c-'))
    ail = Path(a.ail)
    icount = icount_binary()
    rows = []
    try:
        rows.append(bench_library('jellyfish', 'jellyfish', '_jellyfish.py',
                                  WORKLOADS / 'jellyfish_work.py',
                                  a.cpy_site, a.native, a.native_site, a.pypy, ail, work, icount))
        rows.append(bench_library('msgpack', 'msgpack', 'fallback.py',
                                  WORKLOADS / 'msgpack_work.py',
                                  a.cpy_site, a.cpy, None, a.pypy, ail, work, icount))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    Path(a.out).write_text(json.dumps(rows, indent=1) + '\n')
    for r in rows:
        print('%-10s total=%d top=%d native=%d %s' % (
            r['library'], r['functions_total'], r['functions_top_level'],
            r['native_functions'],
            ' '.join('%s=%.3fs' % (k, v) for k, v in r['times'].items())))
    print('icount:', 'unavailable (perf_event_open denied)' if icount is None else str(icount))
    print('wrote %s' % a.out)


if __name__ == '__main__':
    main()
