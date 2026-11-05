#!/usr/bin/env python3
"""Measure whether the C that AIL emits builds and runs correctly with tcc.

    python3 lab/tccprobe/run.py --out /tmp/tccprobe.json

For each program (ten lab/compare AIL sources and forty corpus/gdev programs chosen with a fixed
seed) this generates the C once through `ail_chatgpt.py compile --debug-dir`, which writes the exact
translation unit the compiler saw plus a native report holding the compiler command line.  That same
C is then built three ways:

    gcc -O2   the compiler command line of the build, unchanged
    gcc -O0   the same command line with -O2 replaced by -O0
    tcc       TinyCC, source and the recorded libraries (-lm, ...); gcc-only flags are not passed

Each C build is timed three times (median).  Each binary is run three times on the same input
(median), and stdout, stderr and exit status are compared with the gcc -O2 build.  tcc failures are
sorted into the buckets the task names.  Nothing in the compiler, runtime or default build is
changed; tcc is only ever invoked by this measurement script.
"""
import argparse
import hashlib
import json
import os
import pathlib
import random
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
CORPUS = REPO / 'corpus' / 'gdev'
SEED = 20261105
CASE_TIMEOUT = 120
CORPUS_TIMEOUT = 30
O0_RUN_TIMEOUT = 25

sys.path.insert(0, str(COMPARE))
import run_task as rt  # noqa: E402


def median(values, digits=4):
    return round(statistics.median(values), digits) if values else None


def find_tcc(path):
    if path:
        return pathlib.Path(path)
    found = shutil.which('tcc')
    if found:
        return pathlib.Path(found)
    fallback = pathlib.Path('/tmp/tcc-install/usr/bin/tcc')
    return fallback if fallback.is_file() else None


def generate_c(source, syntax, root, gcc):
    """Run one AIL build; return the C the compiler saw, the recorded flags and the timing."""
    digest = hashlib.sha1(str(source).encode()).hexdigest()[:8]
    work = root / ('gen-' + re.sub(r'[^A-Za-z0-9_]', '_', source.stem) + '-' + digest)
    shutil.rmtree(work, ignore_errors=True)
    for sub in ('cache', 'tmp'):
        (work / sub).mkdir(parents=True)
    dbg = work / 'dbg'
    out = work / 'ail-prog'
    command = [sys.executable, '-B', str(AIL), 'compile', str(source), '-o', str(out), '--debug-dir', str(dbg)]
    if syntax:
        command[5:5] = ['--syntax', syntax]
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'),
               PIPE_CC=gcc, AIL_NO_CACHE='1', AIL_SERVER='0', PYTHONUTF8='1')
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    start = time.perf_counter()
    done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    result = dict(ok=done.returncode == 0, wall=wall, stderr=(done.stderr or done.stdout)[-1200:],
                  work=work, c_files=[], shape='single', flags=[], libs=[])
    report_path = dbg / 'native_report.json'
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding='utf-8'))
        except ValueError:
            report = {}
        result.update(parse_report(report, dbg))
    if not result['c_files']:
        result['c_files'] = sorted(str(p) for p in dbg.glob('*.c'))
    result['c_files'] = [pathlib.Path(p) for p in result['c_files']]
    return result


def _flags_before(body, cut):
    """The compiler flags of a command body up to `cut`, without -o targets and input paths."""
    flags = []
    i = 0
    while i < cut:
        token = body[i]
        if token == '-o':
            i += 2
            continue
        if token.endswith(('.c', '.o', '.a', '.so')):
            i += 1
            continue
        flags.append(token)
        i += 1
    return flags


def _libs_after(body, last_input):
    libs = []
    i = last_input + 1
    while i < len(body):
        token = body[i]
        if token == '-o':
            i += 2
            continue
        if token.startswith(('-l', '-L', '-pthread', '-static')):
            libs.append(token)
        i += 1
    return libs


def parse_report(report, dbg):
    """The translation units, flags and link libraries of the recorded build, from native_report.json."""
    sources = []
    for row in report.get('generated') or []:
        path = row.get('debug_path')
        if path and pathlib.Path(path).is_file():
            sources.append(pathlib.Path(path))
    shape, flags, libs = 'single', [], []
    for operation in report.get('operations') or []:
        body = (operation.get('command') or [])[1:]
        if not body:
            continue
        inputs = [i for i, token in enumerate(body) if token.endswith('.c')]
        if '-c' in body and inputs:
            shape = 'multi'
            flags = flags or _flags_before(body, body.index('-c'))
        elif inputs:
            flags = flags or _flags_before(body, min(body.index('-o'), inputs[0]) if '-o' in body else inputs[0])
            libs = libs or _libs_after(body, inputs[-1])
        else:
            libs = libs or _libs_after(body, -1)
    return dict(c_files=[str(p) for p in sources], shape=shape, flags=flags, libs=libs)


def compiler_flags_for(label, flags, tcc):
    if label == 'tcc':
        return [f for f in flags if f.startswith(('-I', '-D', '-L', '-U'))]
    if label == '-O0':
        replaced = ['-O0' if f == '-O2' else f for f in flags]
        if '-O0' not in replaced:
            replaced.insert(0, '-O0')
        return replaced
    return list(flags)


def build_commands(shape, flags, libs, sources, label, attempt, gcc, tcc):
    if label == 'tcc':
        cc = str(tcc)
    else:
        cc = gcc
    flags = compiler_flags_for(label, flags, tcc)
    attempt.mkdir(parents=True, exist_ok=True)
    if shape == 'single' or len(sources) == 1:
        return [[cc, *flags, str(sources[0]), *libs, '-o', str(attempt / 'prog')]]
    commands, objects = [], []
    for i, source in enumerate(sources):
        obj = attempt / ('u%d.o' % i)
        objects.append(obj)
        commands.append([cc, *flags, '-c', str(source), '-o', str(obj)])
    commands.append([cc, *flags, '-o', str(attempt / 'prog'), *[str(o) for o in objects], *libs])
    return commands


def timed_build(command_fn, runs):
    """Compile `runs` times in a fresh directory each time; the median wall time is the build time."""
    walls, errors, binary = [], [], None
    for i in range(runs):
        commands = command_fn()
        start = time.perf_counter()
        for command in commands:
            done = subprocess.run(command, capture_output=True, text=True)
            if done.returncode:
                errors.append((done.stderr or done.stdout)[-1200:])
                break
        walls.append(time.perf_counter() - start)
        if errors:
            break
        binary = pathlib.Path(commands[-1][commands[-1].index('-o') + 1])
    return dict(ok=not errors and binary is not None and binary.is_file(),
                seconds=median(walls), runs=[round(w, 4) for w in walls],
                stderr=errors[0] if errors else '', binary=binary)


def run_binary(binary, case, root, tag, runs, timeout):
    walls, outs, errs, codes = [], [], [], []
    for i in range(runs):
        stdout_path = root / ('%s-%d.out' % (tag, i))
        stderr_path = root / ('%s-%d.err' % (tag, i))
        stdin = open(case['path'], 'rb') if case.get('stdin') else subprocess.DEVNULL
        start = time.perf_counter()
        try:
            with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
                done = subprocess.run([str(binary), *case.get('args', [])], stdin=stdin,
                                      stdout=out, stderr=err, timeout=timeout)
        except subprocess.TimeoutExpired:
            return dict(timeout=True, seconds=None, runs=[])
        finally:
            if case.get('stdin'):
                stdin.close()
        walls.append(time.perf_counter() - start)
        outs.append(stdout_path.read_bytes())
        errs.append(stderr_path.read_bytes())
        codes.append(done.returncode)
    return dict(timeout=False, seconds=median(walls), runs=[round(w, 4) for w in walls],
                stdout=outs[0], stderr=errs[0], exit=codes[0],
                deterministic=len(set(outs)) == 1 and len(set(errs)) == 1 and len(set(codes)) == 1)


def first_error(text, limit=600):
    lines = [line for line in text.splitlines() if line.strip()]
    chosen = [line for line in lines if 'error' in line.lower()][:3] or lines[:3]
    return '\n'.join(chosen)[:limit]


def c_line(path, number):
    try:
        lines = pathlib.Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return None
    if 1 <= number <= len(lines):
        return lines[number - 1].strip()
    return None


def classify(lowered, line_text):
    """(bucket, construct) from tcc's stderr and the generated C line it pointed at."""
    haystack = (line_text or '').lower() + '\n' + lowered
    if '__int128' in haystack:
        return 'unsupported builtin or intrinsic', '__int128'
    if '__builtin' in haystack or re.search(r'builtin_[a-z_]+', haystack):
        return 'unsupported builtin or intrinsic', None
    if re.search(r'\basm\b|__asm', haystack) or 'inline assembly' in haystack:
        return 'inline asm', None
    if '_thread_local' in haystack or '__thread' in haystack:
        return 'attribute or pragma', 'C11 _Thread_local storage class'
    if '__attribute__' in haystack or '#pragma' in haystack or 'attribute' in haystack:
        return 'attribute or pragma', None
    if 'index too large' in lowered:
        return 'other (tcc parser)', 'unsized struct-array compound literal from runtime values'
    if any(word in lowered for word in ('undefined symbol', 'unresolved', 'undefined reference',
                                        'cannot find', 'file not found', 'relocation')):
        return 'link error', None
    if 'warning: implicit declaration' in lowered and line_text is None:
        return 'link error', 'tcc does not implement the builtin'
    return 'other (tcc parser)', None


def diagnose(stderr, c_files):
    """(bucket, construct, c line number, c line text) for one tcc failure."""
    text = stderr or ''
    line_no, line_text = None, None
    match = re.search(r'\.c:(\d+):\s*(?:error|warning)', text)
    if match:
        line_no = int(match.group(1))
        for c_file in c_files:
            found = c_line(c_file, line_no)
            if found:
                line_text = found
                break
    bucket, construct = classify(text.lower(), line_text)
    return bucket, construct, line_no, line_text


def case_for_task(task, work):
    case = rt.make_case(task, False, work)
    return dict(name=case['name'], stdin=case['stdin'], path=case['path'], args=case['args'])


def measure(source, name, kind, case, root, gcc, tcc, runs):
    generated = generate_c(source, 'python' if source.suffix == '.py' else None, root, gcc)
    record = dict(name=name, kind=kind, source=str(source.relative_to(REPO)),
                  ail_ok=generated['ok'], ail_seconds=round(generated['wall'], 3),
                  c_files=[p.name for p in generated['c_files']],
                  c_bytes=sum(p.stat().st_size for p in generated['c_files']),
                  gcc_flags=generated['flags'], libs=generated['libs'], shape=generated['shape'])
    if not generated['c_files']:
        record['status'] = 'no C emitted'
        record['ail_error'] = first_error(generated['stderr'])
        shutil.rmtree(generated['work'], ignore_errors=True)
        return record
    work = root / ('measure-' + re.sub(r'[^A-Za-z0-9_.-]', '_', name))
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    builds = {}
    for label in ('-O2', '-O0', 'tcc'):
        counter = {'n': 0}

        def commands_for(label=label, counter=counter):
            counter['n'] += 1
            return build_commands(generated['shape'], generated['flags'], generated['libs'],
                                  generated['c_files'], label,
                                  work / ('build' + label + '-%d' % counter['n']), gcc, tcc)

        builds[label] = timed_build(commands_for, runs)

    run_case = dict(case)
    timeout = CASE_TIMEOUT if kind == 'compare' else CORPUS_TIMEOUT
    records = {}
    for label in ('-O2', '-O0', 'tcc'):
        build = builds[label]
        entry = dict(build_ok=build['ok'], build_s=build['seconds'], build_runs=build['runs'])
        if build['ok']:
            # Only -O2 and tcc run times are reported; an -O0 binary is built for its compile time
            # only, so its run is bounded and a slow one is not waited out three times.
            label_timeout = min(timeout, O0_RUN_TIMEOUT) if label == '-O0' else timeout
            entry.update(run_binary(build['binary'], run_case, work, 'run' + label, runs, label_timeout))
        else:
            entry['build_error'] = first_error(build['stderr'])
        records[label] = entry

    reference = records['-O2']
    for label in ('-O0', 'tcc'):
        entry = records[label]
        if (reference.get('build_ok') and not reference.get('timeout') and entry.get('build_ok')
                and not entry.get('timeout')):
            entry['match'] = (entry['stdout'] == reference['stdout'] and entry['stderr'] == reference['stderr']
                              and entry['exit'] == reference['exit'])
        else:
            entry['match'] = False

    record.update(builds={label: dict(ok=records[label]['build_ok'], seconds=records[label]['build_s'],
                                      runs=records[label]['build_runs']) for label in records},
                  runs={label: {key: records[label].get(key) for key in
                                ('seconds', 'runs', 'timeout', 'deterministic', 'match', 'exit',
                                 'stdout_sha', 'stderr_sha')}
                        for label in records},
                  gcc_o2_deterministic=reference.get('deterministic'),
                  gcc_o2_matches_gcc_o0=records['-O0'].get('match'),
                  tcc_matches_gcc_o2=records['tcc'].get('match'))
    for label in records:
        stdout, stderr = records[label].get('stdout'), records[label].get('stderr')
        if stdout is not None:
            record['runs'][label]['stdout_sha'] = hashlib.sha256(stdout).hexdigest()[:16]
            record['runs'][label]['stderr_sha'] = hashlib.sha256(stderr).hexdigest()[:16]
    bucket, construct, line_no, line_text = diagnose(records['tcc'].get('build_error', ''),
                                                     generated['c_files'])
    record['tcc_bucket'] = bucket if (not records['tcc']['build_ok'] or not records['tcc'].get('match')) else None
    record['tcc_construct'] = construct
    record['tcc_error'] = first_error(records['tcc'].get('build_error', ''))
    record['tcc_error_line'] = line_no
    record['tcc_error_line_text'] = (line_text or '')[:400]
    record['tcc_constructs'] = {
        name: sum(len(re.findall(pattern, p.read_text(encoding='utf-8', errors='replace')))
                  for p in generated['c_files'])
        for name, pattern in (('__builtin_', r'__builtin_'), ('__attribute__', r'__attribute__'),
                              ('__asm__', r'__asm__'), ('#pragma', r'#pragma'),
                              ('_Thread_local', r'_Thread_local'), ('__int128', r'__int128'),
                              ('unsized_compound_literal', r'\([A-Za-z_][A-Za-z0-9_]*\[\]\)\{'))}
    shutil.rmtree(generated['work'], ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tcc', help='TinyCC binary (default: tcc on PATH)')
    parser.add_argument('--gcc', default=shutil.which('gcc'), help='gcc used for the reference builds')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--corpus', type=int, default=40)
    parser.add_argument('--runs', type=int, default=3, help='compile and run repetitions; the median is reported')
    parser.add_argument('--out', default='/tmp/tccprobe.json')
    parser.add_argument('--excerpts', help='directory for one short fail_*.txt per tcc failure bucket')
    parser.add_argument('--from-json', help='no measurement: re-print the summary and excerpts of this result file')
    parser.add_argument('--only', choices=('compare', 'corpus'))
    args = parser.parse_args()
    if args.from_json:
        result = json.loads(pathlib.Path(args.from_json).read_text(encoding='utf-8'))
        for record in result['programs'] + result.get('skipped', []):
            if record.get('tcc_bucket'):
                record['tcc_bucket'], record['tcc_construct'] = classify(
                    (record.get('tcc_error') or '').lower(), record.get('tcc_error_line_text'))
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
        print(json.dumps(summarize(result), indent=1))
        return 0
    gcc = args.gcc
    if not gcc:
        parser.error('gcc is required')
    tcc = find_tcc(args.tcc)
    if not tcc or not tcc.is_file():
        parser.error('tcc not found; install it or pass --tcc')
    version = subprocess.run([str(tcc), '-v'], capture_output=True, text=True)
    tcc_version = ((version.stdout or '') + (version.stderr or '')).strip().splitlines()[0]
    gcc_version = subprocess.run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    root = pathlib.Path(tempfile.mkdtemp(prefix='tccprobe-'))
    result = dict(meta=dict(date=time.strftime('%Y-%m-%d'), seed=args.seed, runs=args.runs,
                            tcc=tcc_version, tcc_path=str(tcc),
                            gcc=gcc_version, python=sys.version.split()[0], cpus=os.cpu_count(),
                            corpus=str(CORPUS.relative_to(REPO)), work=str(root)), programs=[])
    try:
        if args.only != 'corpus':
            for task in sorted(p.name for p in (COMPARE / 'src').iterdir() if (p / 'main.ail').is_file()):
                print('== compare', task, file=sys.stderr, flush=True)
                case_dir = root / ('case-' + task)
                case_dir.mkdir(parents=True, exist_ok=True)
                case = case_for_task(task, case_dir)
                record = measure(COMPARE / 'src' / task / 'main.ail', task, 'compare', case,
                                 root, gcc, tcc, args.runs)
                result['programs'].append(record)
                print('   ail=%s tcc=%s bucket=%s' % (record['ail_ok'], record.get('tcc_matches_gcc_o2'),
                                                       record.get('tcc_bucket')), file=sys.stderr, flush=True)
                pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
                shutil.rmtree(case_dir, ignore_errors=True)
        if args.only != 'compare':
            candidates = sorted(CORPUS.glob('*.py'))
            random.Random(args.seed).shuffle(candidates)
            chosen, tried = [], 0
            for source in candidates:
                if len(chosen) >= args.corpus:
                    break
                tried += 1
                print('== corpus', source.stem, '(%d/%d)' % (len(chosen) + 1, args.corpus), file=sys.stderr, flush=True)
                record = measure(source, source.stem, 'corpus', dict(stdin=False, args=[]),
                                 root, gcc, tcc, args.runs)
                if record.get('ail_ok') and record.get('builds', {}).get('-O2', {}).get('ok'):
                    chosen.append(record['name'])
                    result['programs'].append(record)
                    print('   tcc=%s bucket=%s' % (record.get('tcc_matches_gcc_o2'), record.get('tcc_bucket')),
                          file=sys.stderr, flush=True)
                else:
                    record['skipped'] = 'AIL refused or gcc -O2 could not build the emitted C'
                    result.setdefault('skipped', []).append(record)
                    print('   skipped:', record.get('status') or record.get('tcc_bucket'), file=sys.stderr, flush=True)
                pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
            result['meta']['corpus_candidates_tried'] = tried
    finally:
        summary = summarize(result)
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(summary, indent=1))
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
        shutil.rmtree(root, ignore_errors=True)
    return 0


CONSTRUCT_EMITTER = {
    'C11 _Thread_local storage class':
        'AIL_CURRENT/python/pkg-v12/cruntime.py:17245-17246 '
        '(static _Thread_local void *ail__rep_stk[512]); also cruntime.py:30362, jsonrt.py:858',
    'unsized struct-array compound literal from runtime values':
        'AIL_CURRENT/python/pkg-v12/pyfunc.py:24481 '
        "(ail_stdout_parts((ail_str[]){...}, n))",
    'tcc does not implement the builtin':
        'AIL_CURRENT/python/pkg-v12/cruntime.py:433,4044,4065 (__builtin_unreachable), '
        'cruntime.py:3917-3919 and bigint_obj.py:403-411 (__builtin_*_overflow)',
}


def write_excerpts(result, directory):
    """One short fail_*.txt per (bucket, construct), from the first program that hit it."""
    directory.mkdir(parents=True, exist_ok=True)
    seen = {}
    for record in result['programs'] + result.get('skipped', []):
        bucket = record.get('tcc_bucket')
        if not bucket or bucket == 'wrong output':
            continue
        construct = record.get('tcc_construct') or ''
        seen.setdefault((bucket, construct), record)
    for number, ((bucket, construct), record) in enumerate(sorted(seen.items()), 1):
        slug = re.sub(r'[^a-z0-9]+', '_', (bucket + '_' + construct).lower()).strip('_')[:40]
        stderr = record.get('tcc_error') or record.get('ail_error') or ''
        lines = [
            'program: %s (%s)' % (record.get('source'), record.get('kind')),
            'bucket: %s' % bucket,
            'construct: %s' % (construct or '(see the C line)'),
            'tcc stderr:',
            *('  ' + line for line in stderr.splitlines()[:8]),
            'generated C line %s: %s' % (record.get('tcc_error_line'), record.get('tcc_error_line_text')),
            'emitted by: %s' % CONSTRUCT_EMITTER.get(construct, '(see the C line above)'),
        ]
        (directory / ('fail_%d_%s.txt' % (number, slug))).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def summarize(result):
    programs = result['programs']
    attempted = len(programs)
    generated = [p for p in programs if p.get('c_files')]
    baseline = [p for p in generated if p.get('builds', {}).get('-O2', {}).get('ok')]
    tcc_built = [p for p in baseline if p.get('builds', {}).get('tcc', {}).get('ok')]
    matches = [p for p in tcc_built if p.get('tcc_matches_gcc_o2')]
    buckets, constructs = {}, {}
    for p in programs:
        key = p.get('tcc_bucket')
        if key:
            buckets[key] = buckets.get(key, 0) + 1
            construct = p.get('tcc_construct') or (p.get('tcc_error_line_text') or '')[:90]
            if construct:
                constructs[construct] = constructs.get(construct, 0) + 1

    def med_build(label):
        return median([p['builds'][label]['seconds'] for p in programs
                       if p.get('builds', {}).get(label, {}).get('ok')])

    def med_run(label):
        return median([p['runs'][label]['seconds'] for p in programs
                       if p.get('runs', {}).get(label, {}).get('seconds') is not None])

    kinds = {}
    for kind in ('compare', 'corpus'):
        subset = [p for p in programs if p.get('kind') == kind]
        kinds[kind] = dict(attempted=len(subset),
                           gcc_o2_built=sum(1 for p in subset if p.get('builds', {}).get('-O2', {}).get('ok')),
                           tcc_built=sum(1 for p in subset if p.get('builds', {}).get('tcc', {}).get('ok')),
                           tcc_matches=sum(1 for p in subset if p.get('tcc_matches_gcc_o2')))
    return dict(
        attempted=attempted, c_generated=len(generated), gcc_o2_built=len(baseline),
        tcc_built=len(tcc_built), tcc_matches=len(matches),
        tcc_build_failures=len(baseline) - len(tcc_built), wrong_output=len(tcc_built) - len(matches),
        buckets=buckets, constructs=constructs, kinds=kinds,
        corpus_programs=[p['name'] for p in programs if p.get('kind') == 'corpus'],
        median_c_build_s=dict(gcc_O2=med_build('-O2'), gcc_O0=med_build('-O0'), tcc=med_build('tcc')),
        median_run_s=dict(gcc_O2=med_run('-O2'), gcc_O0=med_run('-O0'), tcc=med_run('tcc')),
    )


if __name__ == '__main__':
    sys.exit(main())
