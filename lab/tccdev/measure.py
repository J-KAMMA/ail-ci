#!/usr/bin/env python3
"""Measure whether a tcc development build can close AIL's cold-compile gap with Rust.

    python3 lab/tccdev/measure.py --tcc /tmp/tcc-install/bin/tcc --out lab/tccdev/results.json

For each of the ten lab/compare tasks this records, with medians and spreads of five cold builds:

  gcc total       the current default (`gcc -O2`, one driver call, no build cache, no server)
  gcc split       the same build with a PIPE_CC shim that splits the driver call into `-c` and a
                  link, so the front end (the AIL command minus those two) and each C step are timed
  tcc             the same AIL command with PIPE_CC=tcc and tcc_prelude.h prepended to the C
  run             tcc binary against the gcc binary on the task's performance input
  checks          both binaries against the task's reference.py on every public and hidden case
  guard           gcc -O2 of the C with __TINYC__ forced, to price the portable overflow checks

It also measures the resident server's cold and warm builds with gcc and tcc, and writes JSON.
No default is changed: tcc is only ever invoked through PIPE_CC for this measurement.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
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
COMPARE = REPO / 'lab' / 'compare'
WRAPPER = HERE / 'cc_wrap.py'
PRELUDE = HERE / 'tcc_prelude.h'
RUNS = 5
RUNTIME_RUNS = 5
RUN_TIMEOUT = 300
CASE_TIMEOUT = 120

sys.path.insert(0, str(COMPARE))
import run_task as rt  # noqa: E402


def tasks():
    return sorted(p.name for p in (COMPARE / 'src').iterdir() if (p / 'main.ail').is_file())


def median(values):
    return statistics.median(values)


def summary(values, digits=3):
    if not values:
        return None
    return dict(median=round(median(values), digits), min=round(min(values), digits),
                max=round(max(values), digits), spread='%.3f-%.3f' % (min(values), max(values)),
                runs=[round(v, digits) for v in values])


def build(task, mode, label, root, gcc, tcc, server_dir=None, server=False):
    work = root / ('build-%s-%s-%s' % (task, mode, label))
    shutil.rmtree(work, ignore_errors=True)
    for sub in ('cache', 'tmp', 'logs'):
        (work / sub).mkdir(parents=True)
    out = work / 'prog'
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'), PYTHONUTF8='1')
    env.pop('AIL_NO_CACHE', None)
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    if server:
        env.pop('AIL_SERVER', None)
        env['AIL_SERVER_DIR'] = str(server_dir)
        env['AIL_SERVER_IDLE'] = '30'
    else:
        env['AIL_SERVER'] = '0'
    log = work / 'logs' / 'cc.jsonl'
    if mode != 'gcc':
        env['PIPE_CC'] = str(WRAPPER)
        env['WRAP_LOG'] = str(log)
        env['WRAP_CC'] = str(tcc if mode == 'tcc' else gcc)
        env['WRAP_MODE'] = 'tcc' if mode == 'tcc' else 'split'
        env['WRAP_SAVE_C'] = str(root / 'c')
        env['WRAP_TCC_PRELUDE'] = str(PRELUDE)
    command = [sys.executable, '-B', str(AIL), 'compile', str(COMPARE / 'src' / task / 'main.ail'), '-o', str(out)]
    start = time.perf_counter()
    done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    rows = []
    if log.is_file():
        rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line.strip()]
    compiled = sum(row['compile'] or 0 for row in rows if row['kind'] == 'split')
    linked = sum(row['link'] or 0 for row in rows if row['kind'] == 'split')
    c_part = sum(row.get('total') or 0 for row in rows)
    return dict(ok=done.returncode == 0 and out.is_file(), wall=wall, compile=compiled, link=linked,
                c_part=c_part, rows=rows, out=out, work=work, stderr=done.stderr[-2000:])


def first_error(text):
    for line in text.splitlines():
        if 'error' in line:
            return line[:500]
    return (text.splitlines() or [''])[0][:500]


def extension_counts(text):
    names = ['__builtin_add_overflow', '__builtin_sub_overflow', '__builtin_mul_overflow',
             '__builtin_expect', '__builtin_unreachable', '__builtin_constant_p', '__builtin_clz',
             '__builtin_clzll', '__builtin_memcpy', '__builtin_ia32_pmovmskb256',
             '__builtin_cpu_supports', '__builtin_cpu_init', '__attribute__', '__typeof__',
             'vector_size', 'may_alias', 'target("avx2")', '#pragma omp', 'statement expression']
    counts = {}
    for name in names:
        n = text.count(name)
        if n:
            counts[name] = n
    counts['statement expression'] = len(re.findall(r'\(\{', text))
    counts['__TINYC__ guardable'] = text.count('__builtin_add_overflow') + text.count('__builtin_sub_overflow') + text.count('__builtin_mul_overflow')
    return counts


def run_timed(binary, case, work, tag, reps):
    walls, hashes, codes = [], [], set()
    for i in range(reps):
        out = work / ('run-%s-%d.out' % (tag, i))
        start = time.perf_counter()
        try:
            done = rt.exec_prog([], [str(binary)], case, out, RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            return dict(timeout=True)
        walls.append(time.perf_counter() - start)
        hashes.append(hashlib.sha256(out.read_bytes()).hexdigest())
        codes.add(done.returncode)
    return dict(wall_ms=summary([w * 1000 for w in walls], 1), exit_codes=sorted(codes),
                output_sha256=hashes, deterministic=len(set(hashes)) == 1)


def compile_gcc(source, out, flags, extra=()):
    command = [flags[0], *flags[1:], *extra, str(source), '-o', str(out)]
    start = time.perf_counter()
    done = subprocess.run(command, capture_output=True, text=True)
    return done.returncode == 0, time.perf_counter() - start, done.stderr[-1000:]


def safely_remove(path):
    shutil.rmtree(path, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tcc', default=os.environ.get('TCC', '/tmp/tcc-install/bin/tcc'))
    parser.add_argument('--out', default=str(HERE / 'results.json'))
    parser.add_argument('--runs', type=int, default=RUNS)
    parser.add_argument('--runtime-runs', type=int, default=RUNTIME_RUNS)
    parser.add_argument('--tasks', default='')
    parser.add_argument('--no-server', action='store_true')
    args = parser.parse_args()
    tcc = pathlib.Path(args.tcc)
    gcc = shutil.which('gcc')
    if not gcc:
        parser.error('gcc is required')
    if not tcc.is_file():
        parser.error('tcc not found at %s (install tcc, or build tinycc; see docs/design/TCC_DEV.md)' % tcc)
    WRAPPER.chmod(0o755)
    tcc_version = subprocess.run([str(tcc), '-v'], capture_output=True, text=True)
    tcc_version = (tcc_version.stdout or tcc_version.stderr).splitlines()[0]
    gcc_version = subprocess.run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    chosen = [name.strip() for name in args.tasks.split(',') if name.strip()] or tasks()
    root = pathlib.Path(tempfile.mkdtemp(prefix='tccdev-'))
    (root / 'c').mkdir()
    result = dict(meta=dict(date=time.strftime('%Y-%m-%d'), tcc=tcc_version, gcc=gcc_version,
                            python=sys.version.split()[0], runs=args.runs, runtime_runs=args.runtime_runs,
                            cpus=os.cpu_count(), kernel=os.uname().release, work=str(root)),
                  tasks={})
    for task in chosen:
        print('==', task, file=sys.stderr, flush=True)
        record = {}
        warm = build(task, 'gcc', 'warmup', root, gcc, tcc)
        if not warm['ok']:
            record['build_error'] = warm['stderr']
            result['tasks'][task] = record
            continue
        safely_remove(warm['work'])

        plain = [build(task, 'gcc', 'plain%d' % i, root, gcc, tcc) for i in range(args.runs)]
        record['gcc'] = dict(ok=all(b['ok'] for b in plain),
                             total=summary([b['wall'] for b in plain]),
                             errors=[b['stderr'] for b in plain if not b['ok']][:1])
        split = [build(task, 'split', 'split%d' % i, root, gcc, tcc) for i in range(args.runs)]
        fronts = [b['wall'] - b['compile'] - b['link'] for b in split if b['ok']]
        record['gcc'].update(split_ok=all(b['ok'] for b in split),
                             front=summary(fronts),
                             compile=summary([b['compile'] for b in split if b['ok']]),
                             link=summary([b['link'] for b in split if b['ok']]),
                             split_total=summary([b['wall'] for b in split if b['ok']]),
                             errors=[b['stderr'] for b in split if not b['ok']][:1])
        saved = root / 'c' / 'program.c'
        if saved.is_file():
            (root / 'c' / ('%s.c' % task)).write_bytes(saved.read_bytes())
        source_c = root / 'c' / ('%s.c' % task)
        text = source_c.read_text(encoding='utf-8', errors='replace') if source_c.is_file() else ''
        record['c_bytes'] = len(text.encode('utf-8'))
        record['constructs'] = extension_counts(text)

        tcc_builds = [build(task, 'tcc', 'tcc%d' % i, root, gcc, tcc) for i in range(args.runs)]
        record['tcc'] = dict(ok=all(b['ok'] for b in tcc_builds),
                             total=summary([b['wall'] for b in tcc_builds]),
                             c_part=summary([b['c_part'] for b in tcc_builds if b['ok']]),
                             front=summary([b['wall'] - b['c_part'] for b in tcc_builds if b['ok']]),
                             errors=[b['stderr'] for b in tcc_builds if not b['ok']][:1])
        tcc_source = root / 'c' / 'program.c.tcc.c'
        if tcc_source.is_file():
            (root / 'c' / ('%s.tcc.c' % task)).write_bytes(tcc_source.read_bytes())
        patched_c = root / 'c' / ('%s.tcc.c' % task)
        if text:
            patched_c.write_text(PRELUDE.read_text(encoding='utf-8') + text, encoding='utf-8')

        unpatched = root / ('%s.unpatched' % task)
        start = time.perf_counter()
        raw = subprocess.run([str(tcc), '-o', str(unpatched), str(source_c), '-lm'], capture_output=True, text=True)
        record['tcc']['unpatched'] = dict(ok=raw.returncode == 0, first_error=first_error(raw.stderr) if raw.returncode else None,
                                          seconds=round(time.perf_counter() - start, 3))
        single, comp_only, link_only = [], [], []
        obj = root / ('%s.o' % task)
        for _ in range(args.runs):
            out = root / ('%s.tcc.bin' % task)
            start = time.perf_counter()
            raw = subprocess.run([str(tcc), '-o', str(out), str(patched_c), '-lm'], capture_output=True, text=True)
            single.append(time.perf_counter() - start)
            if raw.returncode:
                record['tcc']['patched_error'] = first_error(raw.stderr)
            start = time.perf_counter()
            raw = subprocess.run([str(tcc), '-c', '-o', str(obj), str(patched_c)], capture_output=True, text=True)
            comp_only.append(time.perf_counter() - start)
            start = time.perf_counter()
            raw = subprocess.run([str(tcc), '-o', str(out), str(obj), '-lm'], capture_output=True, text=True)
            link_only.append(time.perf_counter() - start)
        record['tcc'].update(single=summary(single), compile=summary(comp_only), link=summary(link_only))

        gcc_bin = next((b['out'] for b in split if b['ok']), None)
        tcc_bin = next((b['out'] for b in tcc_builds if b['ok']), None)
        if tcc_bin is None:
            fallback = root / ('%s.tcc.bin' % task)
            if fallback.is_file():
                tcc_bin = fallback

        work = root / ('check-%s' % task)
        work.mkdir()
        case = rt.make_case(task, False, work)
        runtime = {}
        if gcc_bin and pathlib.Path(gcc_bin).is_file():
            runtime['gcc'] = run_timed(gcc_bin, case, work, 'gcc', args.runtime_runs)
        if tcc_bin and pathlib.Path(tcc_bin).is_file():
            runtime['tcc'] = run_timed(tcc_bin, case, work, 'tcc', args.runtime_runs)
        if runtime.get('gcc') and runtime.get('tcc'):
            runtime['match'] = (runtime['gcc']['exit_codes'] == runtime['tcc']['exit_codes']
                                and runtime['gcc']['output_sha256'] == runtime['tcc']['output_sha256'])
        record['runtime'] = runtime
        record['perf_case'] = dict(name=case['name'], input_bytes=case['input_bytes'])

        check = rt.make_check_cases(task, work)
        expected = rt.reference_outputs(task, check, work)
        checks = dict(cases=len(check))
        if gcc_bin and pathlib.Path(gcc_bin).is_file():
            checks['gcc'] = rt.check_cases('gcc', [str(gcc_bin)], check, expected, work)
        if tcc_bin and pathlib.Path(tcc_bin).is_file():
            checks['tcc'] = rt.check_cases('tcc', [str(tcc_bin)], check, expected, work)
        record['checks'] = checks

        if split and split[0]['ok'] and split[0]['rows']:
            row = next((r for r in split[0]['rows'] if r['kind'] == 'split'), None)
            if row:
                compiler_args = row['args']
                flags = []
                skip = False
                for arg in compiler_args:
                    if skip:
                        skip = False
                    elif arg in ('-o', '-MF', '-MT', '-MQ'):
                        skip = True
                    elif arg.endswith('.c'):
                        continue
                    else:
                        flags.append(arg)
                original = root / ('%s.guard.orig' % task)
                guarded = root / ('%s.guard.tinyc' % task)
                ok1, t1, err1 = compile_gcc(source_c, original, [gcc, *flags])
                ok2, t2, err2 = compile_gcc(patched_c, guarded, [gcc, *flags], ['-D__TINYC__'])
                guard = dict(original_ok=ok1, tinyc_ok=ok2, original_compile_s=round(t1, 3), tinyc_compile_s=round(t2, 3))
                if ok1 and ok2:
                    guard['original'] = run_timed(original, case, work, 'guard-orig', args.runtime_runs)
                    guard['tinyc'] = run_timed(guarded, case, work, 'guard-tinyc', args.runtime_runs)
                    if guard['original'].get('wall_ms') and guard['tinyc'].get('wall_ms'):
                        a = guard['original']['wall_ms']['median']
                        b = guard['tinyc']['wall_ms']['median']
                        guard['overhead_pct'] = round(100 * (b - a) / a, 1) if a else None
                else:
                    guard['errors'] = [err1, err2]
                record['guard'] = guard

        if not args.no_server:
            server_record = {}
            for mode in ('gcc', 'tcc'):
                server_dir = root / ('server-%s-%s' % (task, mode))
                cold = build(task, mode, 'server-cold', root, gcc, tcc, server_dir=server_dir, server=True)
                time.sleep(0.5)
                warms = [build(task, mode, 'server-warm%d' % i, root, gcc, tcc, server_dir=server_dir, server=True)
                         for i in range(args.runs)]
                server_record[mode] = dict(cold=round(cold['wall'], 3) if cold['ok'] else None,
                                           warm=summary([b['wall'] for b in warms if b['ok']]),
                                           ok=cold['ok'] and all(b['ok'] for b in warms))
            record['server'] = server_record

        result['tasks'][task] = record
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        print('   gcc %.2fs (front %.2fs) tcc %.2fs run=%s checks=%s/%s' % (
            record['gcc']['total']['median'] if record['gcc'].get('total') else -1,
            record['gcc']['front']['median'] if record['gcc'].get('front') else -1,
            record['tcc']['total']['median'] if record['tcc'].get('total') else -1,
            runtime.get('match'),
            checks.get('tcc', {}).get('cases_public'), checks.get('tcc', {}).get('cases_hidden')),
              file=sys.stderr, flush=True)

    pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print('wrote', args.out, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
