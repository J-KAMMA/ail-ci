#!/usr/bin/env python3
"""Run the opt-in `--cc=tcc` corpus gate and print the comparison table.

The gate builds and runs 160 cases: the ten `lab/compare` tasks, tccprobe1's
fifty programs (the ten compare tasks plus its forty seeded `corpus/gdev`
programs), and the first 100 sorted `lab/corpus/programs/*/*.py`.  Each case is
built with gcc `-O2` (the reference) and with `--cc=tcc` for every tcc binary
passed with `--tcc`.  stdout, stderr and the exit status are compared; a program
the scan refuses is reported with its named message.  The C compiler step is
also timed three times and the median is kept.

    python3 lab/devcc/gate.py \
        --tcc /tmp/tcc027/bin/tcc --tcc /tmp/tcc-mob-install/bin/tcc \
        --json /tmp/devcc3-gate.json

Run it under `ulimit -v 1500000` like the other heavy lab scripts.  It never
touches a default build: only the explicit `--cc=tcc` builds see the mode.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
COMPARE = ROOT / 'lab' / 'compare'
GDEV = ROOT / 'corpus' / 'gdev'
CORPUS = ROOT / 'lab' / 'corpus' / 'programs'
TASKS = ROOT / 'lab' / 'corpus' / 'tasks'

sys.path.insert(0, str(COMPARE))
import run_task as rt  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    'devcc_gate_under_test', ROOT / 'AIL_CURRENT' / 'python' / 'pkg-v12' / 'devcc.py')
devcc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(devcc)

# tccprobe1's RESULTS.md lists these forty seeded corpus programs.  Keeping the
# list here makes the gate select the same fifty programs without rerunning the
# skip loop (five candidates AIL refused were replaced by later ones).
TCCPROBE_CORPUS = (
    'g01_010', 'g02_002', 'g18_038', 'g25_038', 'g05_016', 'g00_004', 'g03_018',
    'g04_016', 'g17_002', 'g04_004', 'g06_000', 'g04_038', 'g17_026', 'g13_014',
    'g18_006', 'g19_018', 'g09_026', 'g22_022', 'g13_038', 'g04_008', 'g16_004',
    'g00_000', 'g21_032', 'g20_000', 'g09_002', 'g22_014', 'g12_038', 'g09_032',
    'g06_004', 'g04_034', 'g03_012', 'g21_020', 'g23_028', 'g03_006', 'g12_008',
    'g18_016', 'g23_032', 'g02_000', 'g13_018', 'g25_000',
)

REFUSAL = re.compile(r'--cc=tcc:[^\n]*')


def compare_tasks():
    return sorted(path.name for path in (COMPARE / 'src').iterdir() if (path / 'main.ail').is_file())


def corpus_input(source):
    path = TASKS / source.stem / 'in0.txt'
    return path if path.is_file() else None


def make_cases(root):
    """The 160 gate cases; duplicate compare tasks are kept because the task counts them twice."""
    cases = []
    case_cache = {}
    for task in compare_tasks():
        work = root / ('case-' + task)
        work.mkdir()
        case = rt.make_case(task, False, work)
        case_cache[task] = dict(stdin=str(case['path']) if case['stdin'] else None,
                                args=list(case['args']))
    for task in compare_tasks():
        cases.append(dict(kind='compare', name=task,
                          source=COMPARE / 'src' / task / 'main.ail', case=case_cache[task]))
    for task in compare_tasks():
        cases.append(dict(kind='tccprobe', name=task,
                          source=COMPARE / 'src' / task / 'main.ail', case=case_cache[task]))
    for name in TCCPROBE_CORPUS:
        cases.append(dict(kind='tccprobe', name=name, source=GDEV / (name + '.py'),
                          case=dict(stdin=None, args=[])))
    for source in sorted(CORPUS.glob('*/*.py'))[:100]:
        stdin = corpus_input(source)
        cases.append(dict(kind='corpus', name=str(source.relative_to(ROOT)), source=source,
                          case=dict(stdin=str(stdin) if stdin else None, args=[])))
    return cases


def clean_env(cache, temporary, path_dir=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith('AIL_')}
    env.update(AIL_CACHE=str(cache), TMPDIR=str(temporary), AIL_NO_CACHE='1', AIL_SERVER='0',
               PYTHONHASHSEED='0', PYTHONUTF8='1', AIL_QUIET_FALLBACK='1')
    if path_dir is not None:
        env['PATH'] = str(path_dir) + os.pathsep + env.get('PATH', '')
    return env


def build(source, work, label, tcc_dir=None):
    cache, temporary = work / (label + '-cache'), work / (label + '-tmp')
    cache.mkdir(exist_ok=True)
    temporary.mkdir(exist_ok=True)
    debug = work / (label + '-dbg')
    output = work / (label + '-prog')
    command = [sys.executable, '-B', str(AIL), 'compile', str(source)]
    if source.suffix == '.py':
        command += ['--syntax', 'python']
    command += ['-o', str(output), '--debug-dir', str(debug)]
    if tcc_dir is not None:
        command.append('--cc=tcc')
    env = clean_env(cache, temporary, tcc_dir)
    start = time.perf_counter()
    try:
        done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=work,
                              timeout=900)
        wall = time.perf_counter() - start
        stderr = (done.stderr or '') + (done.stdout or '')
        return dict(ok=done.returncode == 0 and output.is_file(), code=done.returncode,
                    stderr=stderr, wall=wall, output=output, debug=debug)
    except subprocess.TimeoutExpired:
        return dict(ok=False, code=None, stderr='build timed out', wall=900.0,
                    output=output, debug=debug)


def run_binary(binary, case, timeout):
    stdin = subprocess.DEVNULL
    handle = None
    try:
        if case.get('stdin'):
            handle = open(case['stdin'], 'rb')
            stdin = handle
        start = time.perf_counter()
        done = subprocess.run([str(binary), *case.get('args', [])], stdin=stdin,
                              capture_output=True, timeout=timeout)
        return dict(seconds=time.perf_counter() - start, stdout=done.stdout,
                    stderr=done.stderr, exit=done.returncode, timeout=False)
    except subprocess.TimeoutExpired as error:
        return dict(seconds=timeout, stdout=error.stdout or b'', stderr=error.stderr or b'',
                    exit=None, timeout=True)
    finally:
        if handle is not None:
            handle.close()


def report_commands(report):
    """The recorded C commands with their temporary generated sources mapped to debug copies."""
    generated = {row['path']: row['debug_path'] for row in report.get('generated') or []
                 if row.get('debug_path')}
    commands = []
    for operation in report.get('operations') or []:
        tokens = []
        for token in operation.get('command') or []:
            token = str(token)
            tokens.append(generated.get(token, token))
        if tokens:
            commands.append(tokens)
    return commands


def remap_for_attempt(command, attempt):
    mapped = []
    index = 0
    while index < len(command):
        token = command[index]
        if token == '-o' and index + 1 < len(command):
            mapped.extend([token, str(attempt / Path(command[index + 1]).name)])
            index += 2
            continue
        if os.path.isabs(token) and token.endswith(('.o', '.a', '.so')):
            mapped.append(str(attempt / Path(token).name))
        else:
            mapped.append(token)
        index += 1
    return mapped


def time_commands(commands, work, label, runs=3):
    if not commands:
        return None
    walls = []
    for number in range(runs):
        attempt = work / ('%s-time-%d' % (label, number))
        attempt.mkdir()
        start = time.perf_counter()
        failed = False
        for command in commands:
            done = subprocess.run(remap_for_attempt(command, attempt), capture_output=True)
            if done.returncode:
                failed = True
                break
        walls.append(time.perf_counter() - start)
        if failed:
            return None
    return statistics.median(walls)


def tcc_commands(gcc_commands, tool, sources):
    replaced, directory = devcc._with_prelude(sources)
    commands = []
    for command in gcc_commands:
        rewritten = [str(tool)] + devcc._rewrite_args(command[1:])
        commands.append([replaced.get(os.fspath(token), token) for token in rewritten])
    return commands, directory


def refusal_text(text):
    match = REFUSAL.search(text or '')
    if match is None:
        return None
    return match.group(0).strip()


def first_error(text, limit=600):
    lines = [line for line in (text or '').splitlines() if line.strip()]
    chosen = [line for line in lines if 'error' in line.lower()] or lines[:6]
    return '\n'.join(chosen)[:limit]


def measure_case(case, work, gcc, tcc_paths, path_dirs, run_timeout):
    result = dict(kind=case['kind'], name=case['name'], source=str(case['source'].relative_to(ROOT)),
                  gcc={}, tcc={})
    base = build(case['source'], work, 'gcc')
    result['gcc'] = dict(ok=base['ok'], wall=round(base['wall'], 4),
                         stderr=first_error(base['stderr']) if not base['ok'] else '')
    if not base['ok']:
        return result
    reference = run_binary(base['output'], case['case'], run_timeout)
    result['gcc'].update(run_seconds=round(reference['seconds'], 4),
                         stdout_sha=hashlib.sha256(reference['stdout']).hexdigest()[:16],
                         stderr_sha=hashlib.sha256(reference['stderr']).hexdigest()[:16],
                         exit=reference['exit'], timeout=reference['timeout'])

    report_path = base['debug'] / 'native_report.json'
    gcc_commands = []
    if report_path.is_file():
        try:
            gcc_commands = report_commands(json.loads(report_path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            gcc_commands = []
    result['gcc']['c_step_s'] = time_commands(gcc_commands, work, 'gcc')

    for label, tool in tcc_paths:
        entry = dict(label=label, version=devcc.tcc_version(tool))
        built = build(case['source'], work, 'tcc-' + label, path_dirs[label])
        entry.update(build_seconds=round(built['wall'], 4))
        if not built['ok']:
            refused = refusal_text(built['stderr'])
            if refused is not None:
                entry.update(status='refused', refusal=refused)
            else:
                entry.update(status='failed', error=first_error(built['stderr']))
            result['tcc'][label] = entry
            continue
        entry['build_ok'] = True
        run = run_binary(built['output'], case['case'], run_timeout)
        entry['run_seconds'] = round(run['seconds'], 4)
        if run['timeout']:
            entry['status'] = 'timeout'
        elif (run['stdout'] == reference['stdout'] and run['stderr'] == reference['stderr']
              and run['exit'] == reference['exit']):
            entry['status'] = 'identical'
        else:
            entry['status'] = 'differing'
            entry.update(stdout_sha=hashlib.sha256(run['stdout']).hexdigest()[:16],
                         stderr_sha=hashlib.sha256(run['stderr']).hexdigest()[:16],
                         exit=run['exit'])
        if gcc_commands:
            sources = [str(case['source'])]  # replaced below from the report's debug copies
            try:
                generated = {row['path']: row['debug_path'] for row in
                             json.loads(report_path.read_text(encoding='utf-8')).get('generated') or []
                             if row.get('debug_path')}
                sources = list(generated.values())
            except (OSError, ValueError):
                pass
            commands, directory = tcc_commands(gcc_commands, tool, sources)
            try:
                entry['c_step_s'] = time_commands(commands, work, 'tcc-' + label)
            finally:
                shutil.rmtree(directory, ignore_errors=True)
        result['tcc'][label] = entry
    return result


def summarize(results, versions):
    summary = {}
    for label, tool in versions:
        rows = [result['tcc'][label] for result in results if label in result['tcc']]
        status = Counter(row['status'] for row in rows)
        refusals = Counter(row.get('refusal') for row in rows if row.get('status') == 'refused')
        gcc_c = [result['gcc'].get('c_step_s') for result in results
                 if result['gcc'].get('ok') and result['gcc'].get('c_step_s') is not None]
        tcc_c = [result['tcc'][label].get('c_step_s') for result in results
                 if result['tcc'].get(label, {}).get('c_step_s') is not None]
        paired = [(result['gcc']['c_step_s'], result['tcc'][label]['c_step_s'])
                  for result in results
                  if result['gcc'].get('c_step_s') is not None
                  and result['tcc'].get(label, {}).get('c_step_s') is not None]
        compare_paired = [(result['gcc']['c_step_s'], result['tcc'][label]['c_step_s'])
                          for result in results if result['kind'] == 'compare'
                          and result['gcc'].get('c_step_s') is not None
                          and result['tcc'].get(label, {}).get('c_step_s') is not None]
        summary[label] = dict(
            version='%d.%d.%d' % (devcc.tcc_version(tool) or ()),
            cases=len(rows), gcc_built=sum(1 for r in results if r['gcc'].get('ok')),
            tcc_built=sum(1 for row in rows if row.get('build_ok')),
            identical=status.get('identical', 0), refused=status.get('refused', 0),
            differing=status.get('differing', 0), failed=status.get('failed', 0),
            timeout=status.get('timeout', 0), refusals=dict(refusals.most_common()),
            gcc_c_median=statistics.median(gcc_c) if gcc_c else None,
            tcc_c_median=statistics.median(tcc_c) if tcc_c else None,
            c_pairs=len(paired),
            c_ratio_sum=(sum(g for g, _ in paired) / sum(t for _, t in paired)) if paired else None,
            compare_c_ratio_sum=((sum(g for g, _ in compare_paired) /
                                  sum(t for _, t in compare_paired)) if compare_paired else None),
            compare_c_pairs=len(compare_paired))
    return summary


def markdown(summary):
    lines = ['| tcc | cases | gcc -O2 built | tcc built | identical | refused | differing | failed | timeout | C step gcc (s) | C step tcc (s) | gcc/tcc |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for label, row in summary.items():
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s |' % (
            row['version'] or label, row['cases'], row['gcc_built'], row['tcc_built'],
            row['identical'], row['refused'], row['differing'], row['failed'], row['timeout'],
            'n/a' if row['gcc_c_median'] is None else '%.4f' % row['gcc_c_median'],
            'n/a' if row['tcc_c_median'] is None else '%.4f' % row['tcc_c_median'],
            'n/a' if row['c_ratio_sum'] is None else '%.1fx' % row['c_ratio_sum']))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tcc', action='append', required=True,
                        help='a tcc binary to test; repeat for each version')
    parser.add_argument('--json', help='write the full records here')
    parser.add_argument('--run-timeout', type=float, default=300)
    parser.add_argument('--jobs', type=int, default=1, choices=(1, 2),
                        help='cases measured in parallel (2 at most, like the other lab scripts)')
    parser.add_argument('--limit', type=int, help='debugging only: stop after this many cases')
    args = parser.parse_args()
    gcc = shutil.which('gcc')
    if not gcc:
        parser.error('gcc is required')

    root = Path(tempfile.mkdtemp(prefix='devcc3-gate-'))
    versions, tcc_paths, path_dirs = [], [], {}
    try:
        for index, path in enumerate(args.tcc):
            tool = Path(path).resolve()
            version = devcc.tcc_version(tool)
            label = '%d.%d.%d' % version if version else 'tcc%d' % index
            if label in path_dirs:
                label = '%s-%d' % (label, index)
            alias = root / ('bin-' + label)
            alias.mkdir()
            os.symlink(str(tool), str(alias / 'tcc'))
            path_dirs[label] = alias
            tcc_paths.append((label, str(tool)))
            versions.append((label, str(tool)))
        cases = make_cases(root)
        if args.limit:
            cases = cases[:args.limit]
        # Duplicate sources (the compare tasks are counted twice) are measured once.
        order, jobs = [], {}
        for case in cases:
            key = (str(case['source']), case['case'].get('stdin'),
                   tuple(case['case'].get('args') or ()))
            if key not in jobs:
                number = len(order) + 1
                work = root / ('work-%03d' % number)
                work.mkdir()
                jobs[key] = (case, work)
                order.append(key)
        measured = {}
        done = [0]
        lock = threading.Lock()

        def measure(key):
            case, work = jobs[key]
            result = measure_case(case, work, gcc, tcc_paths, path_dirs, args.run_timeout)
            with lock:
                done[0] += 1
                print('== %d/%d %s %s' % (done[0], len(order), case['kind'], case['name']),
                      file=sys.stderr, flush=True)
                for label, entry in result['tcc'].items():
                    print('   %s: %s' % (label, entry['status']), file=sys.stderr, flush=True)
            return key, result

        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for key, result in pool.map(measure, order):
                measured[key] = result
        results = []
        for case in cases:
            key = (str(case['source']), case['case'].get('stdin'),
                   tuple(case['case'].get('args') or ()))
            source = measured[key]
            results.append(dict(kind=case['kind'], name=case['name'], source=source['source'],
                                gcc=source['gcc'], tcc=source['tcc']))
        summary = summarize(results, versions)
        print(markdown(summary))
        payload = dict(tcc={label: path for label, path in tcc_paths}, summary=summary,
                       results=results)
        if args.json:
            Path(args.json).write_text(json.dumps(payload, indent=1) + '\n', encoding='utf-8')
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
