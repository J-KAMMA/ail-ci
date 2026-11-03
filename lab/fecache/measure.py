#!/usr/bin/env python3
"""Measure the opt-in front-end cache on the lab/compare tasks.

Step 1 prices a warm rebuild with no cache in three cases: unchanged source, one function
body edited, and one imported module edited.  Step 4 measures cold, hit and miss with the
resident server on and off.  The C compiler is wrapped by cc_wrap.py, which splits one
compile+link driver call into `-c` and a link so the front end is `wall - compile - link`.
"""
import argparse
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
TASKS_ROOT = REPO / 'lab' / 'compare' / 'src'
WRAPPER = HERE / 'cc_wrap.py'
DEFAULT_TASKS = ('berth_sim', 'rail_transfer', 'tally_lang')
SYNTHETIC = '''\
def add(a, b):
    return a + b
'''
SYNTHETIC_MAIN = '''\
from lib import add

def main():
    print(add(2, 3))

main()
'''


def summary(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return {'median': round(statistics.median(values), 4),
            'min': round(min(values), 4), 'max': round(max(values), 4),
            'mean': round(statistics.mean(values), 4),
            'stdev': round(statistics.pstdev(values), 4), 'n': len(values)}


def clean_env():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('AIL_') and key != 'PIPE_CC'}
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', AIL_SERVER='0', AIL_NO_CACHE='1')
    return env


def build(source, out, work, tag, fe=False, server_dir=None, save_c=None, cc_cache=False):
    env = clean_env()
    if cc_cache:
        env.pop('AIL_NO_CACHE', None)
        env['AIL_CACHE'] = str(work / 'ail-cache')
    if fe:
        env['AIL_FE_CACHE'] = '1'
        env['AIL_FE_CACHE_DIR'] = str(work / 'fe')
        env['AIL_FE_CACHE_LOG'] = str(work / 'fe.log')
    if server_dir is not None:
        env.pop('AIL_SERVER', None)
        env['AIL_SERVER_DIR'] = str(server_dir)
        env['AIL_SERVER_IDLE'] = '30'
    env['PIPE_CC'] = str(WRAPPER)
    env['WRAP_CC'] = shutil.which('gcc') or 'gcc'
    env['WRAP_MODE'] = 'split'
    log = work / ('cc-%s.jsonl' % tag)
    env['WRAP_LOG'] = str(log)
    if save_c is not None:
        env['WRAP_SAVE_C'] = str(save_c)
    start = time.perf_counter()
    done = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(AIL), 'compile', str(source),
                           '-o', str(out)], cwd=str(work), env=env, capture_output=True,
                          text=True, timeout=1800)
    wall = time.perf_counter() - start
    rows = []
    if log.exists():
        rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    compiled = sum(row.get('compile') or 0.0 for row in rows)
    linked = sum(row.get('link') or 0.0 for row in rows)
    events = []
    event_log = work / 'fe.log'
    if event_log.exists():
        events = event_log.read_text().splitlines()
    return {'ok': done.returncode == 0, 'wall': round(wall, 4),
            'front': round(wall - compiled - linked, 4),
            'compile': round(compiled, 4), 'link': round(linked, 4),
            'cc_calls': len(rows), 'events': events,
            'stderr': done.stderr[-4000:] if done.returncode else ''}


def edit_body(text, number):
    if text.find('def ') >= 0:
        return text + '\nprint("fe-probe-%d")\n' % number
    marker = text.find('fn ')
    brace = text.find('{', marker) if marker >= 0 else -1
    if brace < 0:
        return text + '\nfn fe_probe_%d() { let x = %d; }\n' % (number, number)
    return text[:brace + 1] + '\n    print("fe-probe-%d");\n' % number + text[brace + 1:]


def write_source(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def step1_task(task, runs, root):
    source_text = (TASKS_ROOT / task / 'typed.py').read_text(encoding='utf-8')
    work = root / ('step1-' + task)
    work.mkdir(parents=True)
    source = work / 'main.py'
    result = {'task': task, 'runs': runs, 'cases': {}}

    write_source(source, source_text)
    unchanged = [build(source, work / ('a-%d' % i), work, 'a-%d' % i)
                 for i in range(runs)]
    result['cases']['a_unchanged'] = {key: summary([row[key] for row in unchanged])
                                      for key in ('wall', 'front', 'compile', 'link')}
    result['cases']['a_unchanged']['ok'] = all(row['ok'] for row in unchanged)

    edited = []
    for i in range(runs):
        write_source(source, edit_body(source_text, i))
        edited.append(build(source, work / ('b-%d' % i), work, 'b-%d' % i))
    result['cases']['b_body_edited'] = {key: summary([row[key] for row in edited])
                                        for key in ('wall', 'front', 'compile', 'link')}
    result['cases']['b_body_edited']['ok'] = all(row['ok'] for row in edited)

    result['cases']['c_module_edited'] = {'applicable': False,
                                          'note': 'single-file task; no imported module'}
    return result


def step1_synthetic(runs, root):
    work = root / 'step1-synthetic-import'
    work.mkdir(parents=True)
    source = work / 'main.py'
    library = work / 'lib.py'
    write_source(source, SYNTHETIC_MAIN)
    result = {'task': 'synthetic_import', 'runs': runs, 'cases': {}}

    rows = []
    for i in range(runs):
        write_source(library, SYNTHETIC)
        rows.append(build(source, work / ('a-%d' % i), work, 'a-%d' % i))
    result['cases']['a_unchanged'] = {key: summary([row[key] for row in rows])
                                      for key in ('wall', 'front', 'compile', 'link')}
    result['cases']['a_unchanged']['ok'] = all(row['ok'] for row in rows)

    rows = []
    for i in range(runs):
        write_source(library, SYNTHETIC.replace('a + b', 'a + b + %d' % i))
        rows.append(build(source, work / ('c-%d' % i), work, 'c-%d' % i))
    result['cases']['c_module_edited'] = {key: summary([row[key] for row in rows])
                                          for key in ('wall', 'front', 'compile', 'link')}
    result['cases']['c_module_edited']['ok'] = all(row['ok'] for row in rows)
    return result


def step4_task(task, runs, root, cc_cache=False):
    source_text = (TASKS_ROOT / task / 'typed.py').read_text(encoding='utf-8')
    result = {'task': task, 'runs': runs, 'cc_cache': cc_cache, 'server': {}}
    for server in (False, True):
        label = 'on' if server else 'off'
        rows = {'cold': [], 'hit': [], 'miss': []}
        for i in range(runs):
            work = root / ('step4-%s-%s-%d' % (task, label, i))
            work.mkdir(parents=True)
            source = work / 'main.py'
            write_source(source, source_text)
            server_dir = work / 'server' if server else None
            rows['cold'].append(build(source, work / 'cold', work, 'cold',
                                      fe=True, server_dir=server_dir, cc_cache=cc_cache))
            rows['hit'].append(build(source, work / 'hit', work, 'hit',
                                     fe=True, server_dir=server_dir, cc_cache=cc_cache))
            write_source(source, edit_body(source_text, i))
            rows['miss'].append(build(source, work / 'miss', work, 'miss',
                                      fe=True, server_dir=server_dir, cc_cache=cc_cache))
        result['server'][label] = {}
        for case, found in rows.items():
            result['server'][label][case] = {key: summary([row[key] for row in found])
                                             for key in ('wall', 'front', 'compile', 'link')}
            result['server'][label][case]['ok'] = all(row['ok'] for row in found)
            result['server'][label][case]['events'] = [row['events'][-1] if row['events'] else None
                                                       for row in found]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('step1', 'step4', 'all'), default='all')
    parser.add_argument('--tasks', default=','.join(DEFAULT_TASKS))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--cc-cache', action='store_true')
    parser.add_argument('--no-synthetic', dest='synthetic', action='store_false')
    parser.add_argument('--out', default=str(HERE / 'results.json'))
    args = parser.parse_args()
    tasks = [task.strip() for task in args.tasks.split(',') if task.strip()]
    root = pathlib.Path(tempfile.mkdtemp(prefix='ail-fe-measure-'))
    started = time.time()
    result = {'date': time.strftime('%Y-%m-%d'), 'runs': args.runs,
              'tasks': tasks, 'work': str(root), 'phase': args.phase}
    if args.phase in ('step1', 'all'):
        result['step1'] = {'tasks': [step1_task(task, args.runs, root) for task in tasks]}
        if args.synthetic:
            result['step1']['synthetic_import'] = step1_synthetic(args.runs, root)
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    if args.phase in ('step4', 'all'):
        result['step4'] = {'cc_cache': args.cc_cache,
                           'tasks': [step4_task(task, args.runs, root, args.cc_cache) for task in tasks]}
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    result['elapsed_s'] = round(time.time() - started, 1)
    pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print('wrote', args.out, 'in %.1fs' % result['elapsed_s'], file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
