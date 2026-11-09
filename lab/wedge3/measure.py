#!/usr/bin/env python3
"""wedge3 driver: build the CPython hybrid for real pure-Python library hot modules,
run the observed-type recorder on each workload, and time CPython / PyPy / hybrid /
the Rust rewrite.

    WEDGE_CPY=/path/venv/bin/python WEDGE_PYPY=/path/pypy/bin/python \
        python3 lab/wedge3/measure.py [--only lib,...] [--reps 5] [-o lab/wedge3/results.json]

The libraries themselves are never vendored: `requirements.txt` pins them, they are pip-installed
into the venvs, and only a temporary copy of each hot module is built.  The hybrid compiler is the
obs5 worktree (`WEDGE_AIL`, default ../obs5/AIL_CURRENT), not the base tree.
"""
import argparse
import concurrent.futures
import json
import os
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKLOADS = HERE / 'workloads'
AIL = Path(os.environ.get('WEDGE_AIL', REPO.parent / 'obs5' / 'AIL_CURRENT'))
CPY = os.environ.get('WEDGE_CPY', '/tmp/wedge3venv/bin/python')
PYPY = os.environ.get('WEDGE_PYPY', '/tmp/wedge3pypy/bin/python')
AILCHAT = AIL / 'ail_chatgpt.py'
OBSERVE = AIL / 'ail_observe.py'

PAIRS = [
    {
        'name': 'networkx',
        'workload': 'networkx_bench.py',
        'package': 'networkx',
        'modules': ['networkx.algorithms.shortest_paths.weighted',
                    'networkx.algorithms.shortest_paths.unweighted'],
        'rust': 'rustworkx',
    },
    {
        'name': 'jsonschema',
        'workload': 'jsonschema_bench.py',
        'package': 'jsonschema',
        'modules': ['jsonschema._keywords', 'jsonschema.validators'],
        'rust': 'jsonschema-rs',
    },
    {
        'name': 'chardet',
        'workload': 'chardet_bench.py',
        'package': 'chardet',
        'modules': ['chardet.universaldetector'],
        'rust': 'charset-normalizer',
    },
    {
        'name': 'tomli',
        'workload': 'tomli_bench.py',
        'package': 'tomli',
        'modules': ['tomli._re', 'tomli._parser'],
        'rust': 'rtoml',
    },
    {
        'name': 'difflib',
        'workload': 'difflib_bench.py',
        'package': None,
        'modules': ['difflib'],
        'rust': 'rapidfuzz',
    },
]
SELECTED = [p['name'] for p in PAIRS]
REPS = 5
LIMIT = 2500000 * 1024


def env(extra=None):
    e = dict(os.environ)
    e['AIL_NO_CACHE'] = '1'
    e.pop('AIL_UNIFIED_FORCE', None)
    e.pop('WEDGE_IMPL', None)
    e.pop('WEDGE_HYBRID_DIR', None)
    if extra:
        e.update(extra)
    return e


def _limit():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def run(cmd, cwd=None, timeout=1800, extra_env=None):
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, timeout=timeout,
                       env=env(extra_env), preexec_fn=_limit)
    return p


def module_file(mod):
    p = run([CPY, '-c', 'import %s as m; print(m.__file__)' % mod])
    if p.returncode != 0:
        raise SystemExit('cannot locate %s: %s' % (mod, p.stderr[-400:]))
    return Path(p.stdout.strip())


def rewrite_relative(text, package):
    if not package:
        return text
    text = re.sub(r'^from \.(\w+) import', r'from %s.\1 import' % package, text, flags=re.M)
    text = re.sub(r'^from \. import', r'from %s import' % package, text, flags=re.M)
    return text


def alias_of(mod):
    return mod.rsplit('.', 1)[-1]


def build_hybrid(stage, outdir):
    if outdir.exists():
        shutil.rmtree(outdir)
    p = run([CPY, AILCHAT, 'build', '--cpython', stage, '-o', outdir], cwd='/tmp',
            timeout=2400)
    if not (outdir / 'build.json').is_file():
        raise RuntimeError('build failed for %s:\n%s' % (stage, (p.stdout + p.stderr)[-3000:]))
    data = json.loads((outdir / 'build.json').read_text())
    return data, (p.stdout + p.stderr)


def stage_plain(src, package, path):
    text = rewrite_relative(src.read_text(), package)
    path.write_text(text)


def stage_observed(profile, src, package, path):
    out = path.parent / (path.stem + '.ann.py')
    p = run([CPY, OBSERVE, 'annotate', profile, src, '-o', out])
    if p.returncode != 0 or not out.is_file():
        raise RuntimeError('annotate failed for %s:\n%s' % (src, (p.stdout + p.stderr)[-2000:]))
    text = rewrite_relative(out.read_text(), package)
    path.write_text(text)
    out.unlink()


def copy_hybrid(outdir, alias, dest):
    dest.mkdir(parents=True, exist_ok=True)
    src = outdir / (alias + '.py')
    if not src.is_file():
        raise RuntimeError('generated %s missing in %s' % (alias, outdir))
    shutil.copy2(src, dest / (alias + '.py'))
    for so in outdir.glob('*.so'):
        shutil.copy2(so, dest / so.name)


def record(pair, work):
    profile = work / ('obs_%s.json' % pair['name'])
    t0 = time.perf_counter()
    p = run([CPY, OBSERVE, 'run', '-o', profile, '--all', '--fast', pair['workload']],
            cwd=WORKLOADS, timeout=1800)
    if p.returncode != 0 or not profile.is_file():
        raise RuntimeError('recorder failed for %s:\n%s' % (pair['name'],
                                                            (p.stdout + p.stderr)[-2000:]))
    return profile, time.perf_counter() - t0


def timed(pair, impl, extra, work, reps):
    times = []
    out = None
    for _ in range(reps):
        t0 = time.perf_counter()
        p = run([(PYPY if impl == 'pypy' else CPY), pair['workload']], cwd=WORKLOADS,
                timeout=900, extra_env=extra)
        times.append(time.perf_counter() - t0)
        if p.returncode != 0:
            return {'error': 'exit %d' % p.returncode,
                    'stderr': (p.stderr or '')[-1500:], 'times': times}
        if out is None:
            out = p
    return {'median': statistics.median(times), 'times': times,
            'stdout': out.stdout, 'stderr_last': (out.stderr or '').strip().splitlines()[-1:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=','.join(SELECTED))
    ap.add_argument('--reps', type=int, default=REPS)
    ap.add_argument('-o', '--output', default=str(HERE / 'results.json'))
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    only = [s for s in args.only.split(',') if s]

    if not AILCHAT.is_file():
        raise SystemExit('hybrid compiler not found: %s (set WEDGE_AIL)' % AILCHAT)

    work = Path(tempfile.mkdtemp(prefix='wedge3-'))
    print('workspace', work, flush=True)
    results = {'ail': str(AIL), 'python': run([CPY, '--version']).stdout.strip(),
               'pypy': ((run([PYPY, '--version']).stdout + run([PYPY, '--version']).stderr).strip().splitlines() or ['?'])[-1],
               'pairs': {}, 'workspace': str(work)}
    try:
        for pair in PAIRS:
            if pair['name'] not in only:
                continue
            name = pair['name']
            print('\n==', name, flush=True)
            srcs = [(mod, module_file(mod)) for mod in pair['modules']]
            root = work / name
            root.mkdir(parents=True, exist_ok=True)

            profile, rec_s = record(pair, work)
            print('  recorder %.2fs' % rec_s, flush=True)

            builds = {}
            jobs = []
            for cfg in ('plain', 'obs'):
                for mod, src in srcs:
                    alias = alias_of(mod)
                    stagedir = root / ('stage_%s_%s' % (cfg, alias))
                    stagedir.mkdir(parents=True, exist_ok=True)
                    stage = stagedir / (alias + '.py')
                    if cfg == 'plain':
                        stage_plain(src, pair['package'], stage)
                    else:
                        stage_observed(profile, src, pair['package'], stage)
                    outdir = root / ('build_%s_%s' % (cfg, alias))
                    dest = root / cfg
                    jobs.append((cfg, alias, stage, outdir, dest))

            def do(job):
                cfg, alias, stage, outdir, dest = job
                data, log = build_hybrid(stage, outdir)
                copy_hybrid(outdir, alias, dest)
                return cfg, alias, data, log

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                for cfg, alias, data, log in ex.map(do, jobs):
                    builds.setdefault(cfg, {})[alias] = {
                        'accelerated': data.get('accelerated', []),
                        'rejected': data.get('rejected', {}),
                        'extension': data.get('extension'),
                    }
                    print('  build %-5s %-16s native %d/%d' % (
                        cfg, alias, len(data.get('accelerated', [])),
                        len(data.get('accelerated', [])) + len(data.get('rejected', {}))),
                        flush=True)

            impls = {
                'cpython': (None, {}),
                'pypy': (None, {}),
                'hybrid': (None, {'WEDGE_IMPL': 'hybrid',
                                   'WEDGE_HYBRID_DIR': str(root / 'plain')}),
                'hybrid_obs': (None, {'WEDGE_IMPL': 'hybrid',
                                      'WEDGE_HYBRID_DIR': str(root / 'obs')}),
                'rust': (None, {'WEDGE_IMPL': 'rust'}),
            }
            measured = {}
            order = list(impls)
            for rep in range(args.reps):
                for tag in order:
                    _py, extra = impls[tag]
                    r = timed(pair, tag if tag == 'pypy' else 'cpython', extra, work, 1)
                    measured.setdefault(tag, []).append(r)
                order = order[1:] + order[:1]
            times = {}
            outputs = {}
            for tag, runs in measured.items():
                good = [r for r in runs if 'median' in r]
                if len(good) != len(runs):
                    bad = next(r for r in runs if 'median' not in r)
                    times[tag] = None
                    outputs[tag] = {'error': bad.get('error'), 'stderr': bad.get('stderr')}
                else:
                    times[tag] = statistics.median(r['median'] for r in runs)
                    outputs[tag] = {'stdout': runs[0]['stdout'],
                                    'stderr_last': runs[0]['stderr_last']}

            # equality: hybrid must match CPython byte for byte
            base = outputs.get('cpython', {}).get('stdout')
            checks = {}
            for tag in ('hybrid', 'hybrid_obs', 'pypy'):
                checks[tag] = (outputs.get(tag, {}).get('stdout') == base)
            checks['rust'] = (outputs.get('rust', {}).get('stdout') == base)

            results['pairs'][name] = {
                'workload': pair['workload'],
                'rust_impl': pair['rust'],
                'modules': {mod: str(src) for mod, src in srcs},
                'recorder_s': rec_s,
                'builds': builds,
                'times': times,
                'stdout_match': checks,
                'stdout': {k: v.get('stdout') for k, v in outputs.items()},
                'errors': {k: v for k, v in outputs.items() if 'error' in v},
                'profile': str(profile),
            }
            print('  times', {k: (round(v, 3) if v else v) for k, v in times.items()},
                  'match', checks, flush=True)

        results['reasons'] = analyse_reasons(results)
        Path(args.output).write_text(json.dumps(results, indent=1) + '\n')
        print('\nwrote', args.output, flush=True)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


CATEGORIES = [
    ('not a typed candidate', 'pymix: not a typed candidate'),
    ('method of a class with decorators, bases, a metaclass or class attributes',
     'method: class shape (bases/attributes)'),
    ('a decorated, dunder or non-plain-signature method', 'method: dunder/decorated/signature'),
    ('method: self is stored to or used other than by reading an attribute',
     'method: self use / field write'),
    ('method: calls a method that stays in CPython', 'method: calls a refused method'),
    ('method: field self.', 'method: unsupported field kind'),
    ('a call can raise', 'body: call can raise'),
    ('unresolved-return', 'return kind unresolved'),
    ('list-return', 'list return'),
    ('indexing-can-raise', 'body: indexing can raise'),
    ('division-can-raise', 'body: division can raise'),
    ('not wired to the hybrid ABI', 'typed clone not wired to hybrid ABI'),
    ('reads a module constant', 'module constant'),
]


def categorise(reason):
    for needle, label in CATEGORIES:
        if needle in reason:
            return label
    return reason.split(', stays in CPython')[0].strip() or 'unreported'


def analyse_reasons(results):
    """Charge each refused function's recorder self time to its first refusal reason."""
    out = {}
    for name, rec in results['pairs'].items():
        prof_path = rec.get('profile')
        if not prof_path or not Path(prof_path).is_file():
            continue
        prof = json.loads(Path(prof_path).read_text())
        built_files = set(rec['modules'].values())
        native = set()
        reasons = {}
        for cfg in ('plain',):
            for alias, b in rec['builds'].get(cfg, {}).items():
                native.update(b['accelerated'])
                reasons.update(b['rejected'])
        cats = {}
        outside_cats = {}
        package = next((p['package'] for p in PAIRS if p['name'] == name), None)
        for key, fn in prof['functions'].items():
            fpath = fn.get('file', '')
            self_s = fn.get('self_s') or 0.0
            qn = fn.get('qualname', '')
            if fpath in built_files:
                if qn in native:
                    cat = 'native'
                elif (any(mark in qn for mark in ('<locals>', '<lambda>', '<genexpr>',
                                                  '<listcomp>', '<dictcomp>', '<setcomp>'))):
                    cat = 'nested function / lambda / comprehension'
                elif qn == '<module>':
                    cat = 'module body'
                else:
                    cat = categorise(reasons.get(qn, 'unreported'))
                cats[cat] = cats.get(cat, 0.0) + self_s
            elif package and ('/site-packages/%s/' % package) in fpath:
                cat = 'other library module not built'
                outside_cats[cat] = outside_cats.get(cat, 0.0) + self_s
            elif package is None and fpath == '/usr/lib/python3.12/difflib.py':
                cat = 'other library module not built'
                outside_cats[cat] = outside_cats.get(cat, 0.0) + self_s
        out[name] = {
            'built_module_self_s': round(sum(cats.values()), 4),
            'categories': {k: round(v, 4) for k, v in sorted(cats.items(),
                                                             key=lambda kv: -kv[1])},
            'outside': {k: round(v, 4) for k, v in outside_cats.items()},
        }
    return out


if __name__ == '__main__':
    main()
