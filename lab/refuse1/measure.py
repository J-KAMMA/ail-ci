#!/usr/bin/env python3
"""refuse1: the first hybrid refusal for every top-level function and method in the
wedge3/wedge3b hot modules, with and without observed kinds, weighted by CPython cProfile time.

Measurement only: no compiler or library source is changed.  The hybrid is the obs5 worktree
(`REFUSE_AIL`, default `../obs5/AIL_CURRENT`).  Libraries are pip-installed into throw-away venvs
from the pins recorded in `lab/wedge3/` and `lab/wedge3/wedge3b/`; their source is never vendored.

    REFUSE_CPY3=/tmp/r1/v3/bin/python REFUSE_CPY3B=/tmp/r1/v3b/bin/python \
        python3 lab/refuse1/measure.py -o lab/refuse1/results.json

The workload copies under `workloads/` are byte-identical to the files on branches
job-wedge3-11091201 and job-wedge3b-11091226, so the profiled work is the same work.
"""
import argparse
import ast
import collections
import json
import os
import pstats
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKLOADS = HERE / 'workloads'
AIL = Path(os.environ.get('REFUSE_AIL', REPO.parent / 'obs5' / 'AIL_CURRENT'))
AILCHAT = AIL / 'ail_chatgpt.py'
OBSERVE = AIL / 'ail_observe.py'
PY3 = os.environ.get('REFUSE_CPY3', '/tmp/r1/v3/bin/python')
PY3B = os.environ.get('REFUSE_CPY3B', '/tmp/r1/v3b/bin/python')
LIMIT = 2500000 * 1024

PAIRS = [
    {'name': 'networkx', 'python': PY3, 'package': 'networkx',
     'workload': 'networkx_bench.py',
     'modules': ['networkx.algorithms.shortest_paths.weighted',
                 'networkx.algorithms.shortest_paths.unweighted']},
    {'name': 'jsonschema', 'python': PY3, 'package': 'jsonschema',
     'workload': 'jsonschema_bench.py',
     'modules': ['jsonschema._keywords', 'jsonschema.validators']},
    {'name': 'chardet', 'python': PY3, 'package': 'chardet',
     'workload': 'chardet_bench.py',
     'modules': ['chardet.universaldetector']},
    {'name': 'tomli', 'python': PY3, 'package': 'tomli',
     'workload': 'tomli_bench.py',
     'modules': ['tomli._re', 'tomli._parser']},
    {'name': 'difflib', 'python': PY3, 'package': None,
     'workload': 'difflib_bench.py',
     'modules': ['difflib']},
    {'name': 'pydantic', 'python': PY3B, 'package': 'pydantic',
     'workload': 'pydantic_records.py',
     'modules': ['pydantic.main', 'pydantic.fields', 'pydantic.validators',
                 'pydantic.class_validators', 'pydantic.utils']},
    {'name': 'sqlparse', 'python': PY3B, 'package': 'sqlparse',
     'workload': 'sql_workload.py',
     'modules': ['sqlparse.sql', 'sqlparse.engine.grouping', 'sqlparse.utils',
                 'sqlparse.lexer', 'sqlparse.engine.statement_splitter',
                 'sqlparse.tokens', 'sqlparse.filters.reindent']},
]


def env(extra=None):
    e = dict(os.environ)
    e['AIL_NO_CACHE'] = '1'
    e.pop('AIL_UNIFIED_FORCE', None)
    e.pop('WEDGE_IMPL', None)
    e.pop('WEDGE_HYBRID_DIR', None)
    if extra:
        e.update(extra)
    return e


def limit():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def run(cmd, cwd=None, timeout=2400):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=timeout,
                          env=env(), preexec_fn=limit)


def module_file(python, mod):
    p = run([python, '-c', 'import %s as m; print(m.__file__)' % mod])
    if p.returncode:
        raise SystemExit('cannot locate %s: %s' % (mod, p.stderr[-600:]))
    return Path(p.stdout.strip())


def profile_workload(pair, work):
    out = work / ('%s_cprofile.prof' % pair['name'])
    p = run([pair['python'], '-m', 'cProfile', '-o', out, pair['workload']], cwd=WORKLOADS,
            timeout=1800)
    if p.returncode or not out.is_file():
        raise RuntimeError('cProfile failed for %s:\n%s' % (pair['name'],
                                                           (p.stdout + p.stderr)[-2000:]))
    return out


def observe_workload(pair, work):
    out = work / ('%s_obs.json' % pair['name'])
    p = run([pair['python'], OBSERVE, 'run', '-o', out, '--all', '--fast', pair['workload']],
            cwd=WORKLOADS, timeout=1800)
    if p.returncode or not out.is_file():
        raise RuntimeError('recorder failed for %s:\n%s' % (pair['name'],
                                                           (p.stdout + p.stderr)[-2000:]))
    return out


def units_of(source):
    """(qualname, kind, lineno, decorator lines) for top-level defs and methods of top-level
    classes: the unit set the hybrid's top-level-function and method passes can look at."""
    tree = ast.parse(source)
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, 'function', node.lineno,
                        [d.lineno for d in node.decorator_list]))
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(('%s.%s' % (node.name, sub.name), 'method', sub.lineno,
                                [d.lineno for d in sub.decorator_list]))
    return out


def build_module(python, source, staged, outdir, profile):
    if staged.parent.exists():
        shutil.rmtree(staged.parent)
    staged.parent.mkdir(parents=True)
    if profile is not None:
        p = run([python, OBSERVE, 'annotate', profile, source, '-o', staged])
        if p.returncode or not staged.is_file():
            shutil.copy2(source, staged)
            annotate_error = (p.stdout + p.stderr)[-600:]
        else:
            annotate_error = None
    else:
        shutil.copy2(source, staged)
        annotate_error = None
    if outdir.exists():
        shutil.rmtree(outdir)
    p = run([python, AILCHAT, 'build', '--cpython', staged.name, '-o', outdir],
            cwd=staged.parent)
    rec = {'annotate_error': annotate_error, 'returncode': p.returncode}
    report_path = outdir / 'build.json'
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        rec['accelerated'] = sorted(report.get('accelerated') or [])
        rec['rejected'] = report.get('rejected') or {}
        rec['note'] = report.get('note') or ''
        rec['extension'] = report.get('extension')
    else:
        rec['accelerated'] = []
        rec['rejected'] = {}
        rec['note'] = (p.stdout + p.stderr).strip().splitlines()[-1:] or ['build produced no build.json']
        rec['note'] = rec['note'][0] if isinstance(rec['note'], list) else rec['note']
        rec['extension'] = None
    return rec


def canonical(raw):
    """The first refusal gate, with dynamic field/callee names folded into one group."""
    if raw == 'native':
        return 'native'
    s = re.sub(r', stays in CPython$', '', raw).strip()
    if s.startswith('not a typed candidate'):
        return 'not a typed candidate (pymix cannot express a parameter/return kind or no unit)'
    if s.startswith('the typed clone is not wired to the hybrid ABI'):
        return 'the typed clone is not wired to the hybrid ABI'
    if s.startswith('method of a class with decorators'):
        return 'method: class shape (decorators, bases, metaclass or class attributes)'
    if s.startswith('method of a class that defines a name twice'):
        return 'method: class defines a name twice'
    if s.startswith('a decorated, dunder or non-plain-signature method'):
        return 'method: decorated, dunder or non-plain-signature'
    if s.startswith('a name starting with __ail_'):
        return 'a name starting with __ail_'
    if s.startswith('method: '):
        d = s[len('method: '):]
        if d.startswith('calls self.') and 'not a plain method of the class' in d:
            return 'method: calls a method that is not a plain method'
        if d.startswith('field self.') and 'has no scalar or int/float list kind' in d:
            return 'method: field kind not expressible'
        if d.startswith('calls a method that stays in CPython'):
            return 'method: calls a method that stays in CPython'
        if d.startswith('self is stored to or used other than by reading an attribute'):
            if 'field write-back is opt-in' in d:
                return 'method: writes a self field (write-back is opt-in)'
            return 'method: self used other than reading a field'
        if d.startswith('a loop-free body would copy a list field'):
            return 'method: loop-free body would copy a list field'
        if d.startswith('stores a field that is not one int field'):
            return 'method: stores a non-single-int field'
        if d.startswith('stores a field and calls a method'):
            return 'method: stores a field and calls a method'
        if d.startswith('stores a field and returns a value'):
            return 'method: stores a field and returns a value'
        if d.startswith('a nested scope uses self'):
            return 'method: a nested scope uses self'
        if d.startswith('global statement'):
            return 'method: global statement'
        return 'method: ' + d.split(',')[0].split(':')[0]
    if s.startswith('result kind '):
        return 'result kind is not a hybrid ABI kind'
    if s.startswith('parameter kind '):
        return 'parameter kind is not a hybrid ABI kind'
    if s.startswith('list result: '):
        return 'list result proof failed'
    if s.startswith('a return value is not always '):
        return 'a return value is not always the annotated kind'
    if s.startswith("the typed clone's C signature"):
        return "the typed clone's C signature is not one the hybrid calls"
    if s.startswith('needs an int beyond int64'):
        return 'needs an int beyond int64'
    if s.startswith('may overflow but does not return an int'):
        return 'may overflow but does not return an int'
    if s.startswith('may overflow and has no overflow signal'):
        return 'may overflow and has no overflow signal'
    if s.startswith('the program compares numbers with `is`'):
        return 'the program compares numbers with `is`'
    if s.startswith('the list parameter is mutated'):
        return 'the list parameter is mutated'
    if s.startswith('int(<str>)'):
        return 'int(<str>) parser not cut down'
    if s.startswith('module constant '):
        return 'module constant cannot be guarded'
    if s.startswith('mutual recursion'):
        return 'mutual recursion stays in CPython'
    if s.startswith('more than one recursive function'):
        return 'more than one recursive function stays in CPython'
    # body gates from _unsafe_body / _link_natives
    return s


def cprofile_units(pair, prof_path, modules):
    """{(realpath, name): [(qualname, lineno-set)]}, stats keyed by file+function name."""
    by_file = {}
    for mod, path, units in modules:
        by_file.setdefault(os.path.realpath(path), {})[mod] = units
    stats = pstats.Stats(str(prof_path))
    per_unit = collections.defaultdict(float)
    hot_total = 0.0
    workload_total = 0.0
    for (filename, lineno, name), (_cc, _nc, tt, _ct, _callers) in stats.stats.items():
        workload_total += tt
        real = os.path.realpath(filename)
        mod_units = by_file.get(real)
        if mod_units is None:
            continue
        # pstats gives the bare function name; pick the same-named unit whose def or decorator
        # line is closest (methods of different classes may share a name).
        cands = []
        for mod, units in mod_units.items():
            for qual, kind, defline, decls in units:
                fname = qual.rsplit('.', 1)[-1] if kind == 'method' else qual
                if fname == name:
                    lines = set(decls) | {defline}
                    cands.append((0 if lineno in lines else min(abs(lineno - x) for x in lines),
                                  mod, qual))
        if not cands:
            continue
        _dist, mod, qual = min(cands, key=lambda c: (c[0], c[1], c[2]))
        per_unit[(mod, qual)] += tt
        hot_total += tt
    return per_unit, hot_total, workload_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=','.join(p['name'] for p in PAIRS))
    ap.add_argument('-o', '--output', default=str(HERE / 'results.json'))
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    only = {s for s in args.only.split(',') if s}
    if not AILCHAT.is_file():
        raise SystemExit('hybrid compiler not found: %s (set REFUSE_AIL)' % AILCHAT)

    work = Path(tempfile.mkdtemp(prefix='refuse1-'))
    results = {
        'schema': 'ail.refuse1/1',
        'ail': str(AIL),
        'ail_commit': run(['git', '-C', str(AIL.parent), 'rev-parse', 'HEAD']).stdout.strip(),
        'python3': run([PY3, '--version']).stdout.strip(),
        'python3b': run([PY3B, '--version']).stdout.strip(),
        'pairs': {},
        'tables': {},
    }
    try:
        for pair in PAIRS:
            if pair['name'] not in only:
                continue
            name = pair['name']
            print('\n==', name, flush=True)
            prof_path = profile_workload(pair, work)
            obs_profile = observe_workload(pair, work)
            modules = []
            for mod in pair['modules']:
                path = module_file(pair['python'], mod)
                modules.append((mod, path, units_of(path.read_text(encoding='utf-8'))))
            print('  modules', [(m, len(u)) for m, _p, u in modules], flush=True)

            jobs = []
            for cfg in ('plain', 'obs'):
                for mod, path, _units in modules:
                    safe = mod.replace('.', '_')
                    stage = work / ('src_%s_%s' % (cfg, safe)) / (path.stem + '.py')
                    outdir = work / ('build_%s_%s' % (cfg, safe))
                    jobs.append((cfg, mod, path, stage, outdir, None if cfg == 'plain' else obs_profile))

            def do(job):
                cfg, mod, path, stage, outdir, profile = job
                return cfg, mod, build_module(pair['python'], path, stage, outdir, profile)

            builds = {'plain': {}, 'obs': {}}
            with ThreadPoolExecutor(max_workers=2) as ex:
                for cfg, mod, rec in ex.map(do, jobs):
                    builds[cfg][mod] = rec
                    print('  build %-5s %-46s native %-2d rejected %-3d %s' % (
                        cfg, mod, len(rec['accelerated']), len(rec['rejected']),
                        rec['note'][:90]), flush=True)

            per_unit, hot_total, workload_total = cprofile_units(pair, prof_path, modules)
            pair_rec = {
                'workload': pair['workload'],
                'modules': {mod: str(path) for mod, path, _u in modules},
                'unit_counts': {mod: len(u) for mod, _p, u in modules},
                'cprofile_self_s_in_hot_modules': round(hot_total, 6),
                'cprofile_self_s_whole_workload': round(workload_total, 6),
                'builds': builds,
                'functions': {},
            }
            for cfg in ('plain', 'obs'):
                rows = []
                for mod, path, units in modules:
                    rec = builds[cfg][mod]
                    accel = set(rec['accelerated'])
                    rej = rec['rejected']
                    for qual, kind, _defline, _decls in units:
                        if qual in accel:
                            raw = 'native'
                        elif qual in rej:
                            raw = rej[qual]
                        else:
                            raw = 'not recorded (silent refusal)'
                        rows.append({
                            'module': mod,
                            'qualname': qual,
                            'kind': kind,
                            'reason_raw': raw,
                            'reason': canonical(raw),
                            'self_s': round(per_unit.get((mod, qual), 0.0), 6),
                        })
                pair_rec['functions'][cfg] = rows
            results['pairs'][name] = pair_rec
            for cfg in ('plain', 'obs'):
                n = sum(len(r) for r in (results['pairs'][m]['functions'][cfg]
                                         for m in results['pairs']))
                native = sum(1 for m in results['pairs'] for r in results['pairs'][m]['functions'][cfg]
                             if r['reason'] == 'native')
                print('  %-5s units %d native %d' % (cfg, n, native), flush=True)

        results['tables'] = make_tables(results)
        results['reason_changes_plain_to_obs'] = reason_changes(results)
        Path(args.output).write_text(json.dumps(results, indent=1) + '\n', encoding='utf-8')
        print('\nwrote', args.output, flush=True)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


def make_tables(results):
    tables = {}
    workload_s = sum(rec['cprofile_self_s_whole_workload'] for rec in results['pairs'].values())
    for cfg in ('plain', 'obs'):
        rows = []
        total_units = 0
        total_s = 0.0
        groups = collections.defaultdict(lambda: {'count': 0, 'self_s': 0.0,
                                                  'example': None, 'raw': collections.Counter(),
                                                  'modules': collections.Counter()})
        for name, rec in results['pairs'].items():
            for r in rec['functions'][cfg]:
                total_units += 1
                total_s += r['self_s']
                g = groups[r['reason']]
                g['count'] += 1
                g['self_s'] += r['self_s']
                g['raw'][r['reason_raw']] += 1
                g['modules'][r['module']] += 1
                if g['example'] is None or r['self_s'] > g['example'][0]:
                    g['example'] = (r['self_s'], '%s:%s' % (r['module'], r['qualname']))
        for reason, g in groups.items():
            rows.append({
                'reason': reason,
                'count': g['count'],
                'function_share_pct': round(100.0 * g['count'] / total_units, 2) if total_units else 0.0,
                'self_s': round(g['self_s'], 4),
                'time_share_pct': round(100.0 * g['self_s'] / total_s, 2) if total_s else 0.0,
                'whole_workload_share_pct': round(100.0 * g['self_s'] / workload_s, 2) if workload_s else 0.0,
                'example': g['example'][1] if g['example'] else '',
                'modules': dict(g['modules']),
                'raw_reasons': dict(g['raw']),
            })
        rows.sort(key=lambda r: (-r['self_s'], -r['count'], r['reason']))
        tables[cfg] = {
            'units': total_units,
            'self_s': round(total_s, 4),
            'whole_workload_self_s': round(workload_s, 4),
            'rows': rows,
            'top3_time_share_pct': round(sum(r['time_share_pct'] for r in rows[:3]), 2),
        }
    return tables


def reason_changes(results):
    """Functions whose first refusal gate changed when observed kinds were written in."""
    out = []
    for name, rec in results['pairs'].items():
        plain = {(r['module'], r['qualname']): r for r in rec['functions']['plain']}
        for r in rec['functions']['obs']:
            a = plain[(r['module'], r['qualname'])]
            if a['reason'] != r['reason']:
                out.append({'library': name, 'module': r['module'], 'qualname': r['qualname'],
                            'plain': a['reason'], 'obs': r['reason'],
                            'plain_raw': a['reason_raw'], 'obs_raw': r['reason_raw'],
                            'self_s': r['self_s']})
    out.sort(key=lambda x: (-x['self_s'], x['library'], x['qualname']))
    return out


if __name__ == '__main__':
    main()
