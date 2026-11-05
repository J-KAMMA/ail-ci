#!/usr/bin/env python3
"""Measure whether the C that AIL emits compiles and runs with MIR's c2m.

    python3 lab/devcc/run.py --mir ~/scratch/mir --out /tmp/devcc.json

This is devcc1's measurement: it reuses lab/tccprobe/run.py for the corpus selection, the C
generation (`compile --debug-dir`) and the gcc -O2 reference, and adds a c2m arm.

c2m has no ELF writer: `c2m prog.c -o prog` writes binary MIR (MIR_read input), and the runnable
modes execute C in-process:

    -ei  interpret
    -eg  generate machine code, then run        (the mode the task names)
    -el  lazily generate machine code, then run
    -eb  lazily generate basic-block code, then run

`mir-bin-run prog.bmir <argv0> [args]` runs a binary-MIR file and reads libc/libm/libpthread
symbols through dlopen.  This script uses `c2m -c` to measure the C->binary-MIR compile time,
`mir-bin-run` to measure run time and compare outputs, and `c2m -eg` as a cross-check of the
literal command the task names.  Nothing in the compiler, runtime or default build is changed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import random
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
COMPARE = REPO / 'lab' / 'compare'
CORPUS = REPO / 'corpus' / 'gdev'
SEED = 20261105
CASE_TIMEOUT = 120
CORPUS_TIMEOUT = 30
MEM_LIMIT = 1500 * 1024 * 1024


def _load_tccprobe():
    path = REPO / 'lab' / 'tccprobe' / 'run.py'
    spec = importlib.util.spec_from_file_location('tccprobe_run', path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(COMPARE))
    spec.loader.exec_module(module)
    return module


tp = _load_tccprobe()


def median(values, digits=4):
    return round(statistics.median(values), digits) if values else None


def _limit_memory():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT, MEM_LIMIT))
    except (ValueError, OSError):
        pass


def run_cmd(command, cwd, stdin_path, timeout):
    """Run one process; return wall seconds, child CPU seconds, stdout, stderr and exit status."""
    stdout_path = cwd / ('stdout-%d' % os.getpid())
    stderr_path = cwd / ('stderr-%d' % os.getpid())
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdin = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    try:
        with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
            done = subprocess.run(command, cwd=cwd, stdin=stdin, stdout=out, stderr=err,
                                  timeout=timeout, preexec_fn=_limit_memory)
    except subprocess.TimeoutExpired:
        if stdin is not subprocess.DEVNULL:
            stdin.close()
        return dict(timeout=True, wall=None, cpu=None, stdout=b'', stderr=b'', exit=None)
    finally:
        if stdin is not subprocess.DEVNULL:
            stdin.close()
    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    return dict(timeout=False, wall=wall, cpu=cpu, stdout=stdout_path.read_bytes(),
                stderr=stderr_path.read_bytes(), exit=done.returncode,
                stdout_path=stdout_path, stderr_path=stderr_path)


def run_repeated(command_fn, cwd, stdin_path, timeout, runs):
    walls, cpus, outs, errs, codes = [], [], [], [], []
    for i in range(runs):
        result = run_cmd(command_fn(i), cwd, stdin_path, timeout)
        if result['timeout']:
            return dict(timeout=True, wall=None, cpu=None, runs=[])
        walls.append(result['wall'])
        cpus.append(result['cpu'])
        outs.append(result['stdout'])
        errs.append(result['stderr'])
        codes.append(result['exit'])
    return dict(timeout=False, wall=median(walls), cpu=median(cpus),
                runs=[round(w, 4) for w in walls],
                stdout=outs[0], stderr=errs[0], exit=codes[0],
                deterministic=len(set(outs)) == 1 and len(set(errs)) == 1 and len(set(codes)) == 1,
                stdout_path=None, stderr_path=None)


def c2m_flags(flags):
    """Only the flags c2m also understands; gcc -O2/-f.../-Werror... are not passed."""
    return [f for f in flags if f.startswith(('-I', '-D', '-U'))]


def module_name(c_file, index):
    return 'ail_u%d' % index


def c2m_prepare(sources, flags, attempt, mir, m2b):
    """Write the c2m command sequence; multi-unit builds combine textual MIR with m2b."""
    incs = c2m_flags(flags)
    attempt.mkdir(parents=True, exist_ok=True)
    binary = attempt / 'prog.bmir'
    if len(sources) == 1:
        return [[str(mir), '-O2', *incs, '-c', '-o', str(binary), str(sources[0])]], binary, None
    commands = []
    for i, source in enumerate(sources):
        commands.append([str(mir), '-O2', *incs, '-S', '-o', str(attempt / ('u%d.mir' % i)), str(source)])
    combined = attempt / 'all.mir'
    return commands, binary, dict(units=[attempt / ('u%d.mir' % i) for i in range(len(sources))],
                                  combined=combined, m2b=m2b, binary=binary)


def c2m_finish(state, attempt):
    if state is None:
        return True, ''
    with open(state['combined'], 'w') as out:
        for i, unit in enumerate(state['units']):
            lines = unit.read_text(encoding='utf-8', errors='replace').splitlines(True)
            if lines:
                out.write('%s: module\n' % module_name(None, i))
                out.writelines(lines[1:])
    with open(state['combined'], 'rb') as source, open(state['binary'], 'wb') as target:
        done = subprocess.run([str(state['m2b'])], stdin=source, stdout=target,
                              stderr=subprocess.PIPE, preexec_fn=_limit_memory)
    if done.returncode:
        return False, done.stderr.decode('utf-8', 'replace')[-1200:]
    return state['binary'].is_file(), ''


def timed_c2m_build(sources, flags, root, mir, m2b, runs):
    walls, errors, binary = [], [], None
    for i in range(runs):
        attempt = root / ('c2m-build-%d' % i)
        shutil.rmtree(attempt, ignore_errors=True)
        commands, binary, state = c2m_prepare(sources, flags, attempt, mir, m2b)
        started = time.perf_counter()
        for command in commands:
            done = subprocess.run(command, capture_output=True, text=True, preexec_fn=_limit_memory)
            if done.returncode:
                # Keep the head: the first error is what stops the build. A long tail would drop
                # the root cause (c2m prints every follow-on syntax error after it).
                errors.append((done.stderr or done.stdout or '')[:8000])
                break
        if not errors:
            ok, error = c2m_finish(state, attempt)
            if not ok:
                errors.append(error)
        walls.append(time.perf_counter() - started)
        if errors:
            break
    ok = not errors and binary is not None and binary.is_file()
    return dict(ok=ok, seconds=median(walls), runs=[round(w, 4) for w in walls],
                stderr=errors[0] if errors else '', binary=binary)


def c2m_diagnose(stderr, c_files):
    """(bucket, construct, line number, C line) for one c2m failure."""
    text = (stderr or '')
    lowered = text.lower()
    line_no, line_text, named = None, None, None
    # c2m prints warnings (e.g. out-of-range float literals) before the first error; the first
    # construct that stops the build is the first error/excess/unfinished diagnostic, not a warning.
    located = re.findall(r'(\S+\.c):(\d+):(\d+):\s*(.+)', text)
    for path_text, number, _column, message in located:
        if any(word in message.lower() for word in
               ('syntax error', 'excess elements', 'error', 'unfinished', 'invalid', 'expected')):
            line_no = int(number)
            named = pathlib.Path(path_text).name
            break
    if line_no is not None:
        ordered = ([p for p in c_files if pathlib.Path(p).name == named]
                   + [p for p in c_files if pathlib.Path(p).name != named])
        for c_file in ordered:
            found = tp.c_line(c_file, line_no)
            if found:
                line_text = found
                break
    # Classify from the diagnostic message first. The C line is used only for constructs the
    # message names generically (c2m says `syntax error on identifier` for `__int128`).
    message = ' '.join(match[3] for match in located[:3]).lower()
    line_lower = (line_text or '').lower()
    symbol = re.search(r"can not load symbol\s+(\S+)", text)
    if '__uint128_t' in line_lower or '__uint128_t' in message:
        return 'unsupported builtin or intrinsic', '__uint128_t', line_no, line_text
    if '__int128' in line_lower or '__int128' in message:
        return 'unsupported builtin or intrinsic', '__int128', line_no, line_text
    if symbol:
        name = symbol.group(1)
        if '__builtin_' in name:
            return 'unsupported builtin or intrinsic', name, line_no, line_text
        if 'asm' in name:
            return 'inline asm', name, line_no, line_text
        return 'link error', name, line_no, line_text
    if '_generic' in message or '_generic' in line_lower:
        return 'other (c2m parser)', '_Generic inside __typeof__ (ail_len_t typedef)', line_no, line_text
    if 'excess elements in scalar initializer' in message and line_text and re.search(
            r'\(\s*(?:struct\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\[\s*\]\s*\)\s*\{', line_text):
        return 'other (c2m parser)', 'unsized struct-array compound literal from runtime values', line_no, line_text
    if 'pragma' in message:
        return 'attribute or pragma', None, line_no, line_text
    if '_thread_local' in line_lower or '__thread' in line_lower:
        return 'attribute or pragma', 'C11 _Thread_local storage class', line_no, line_text
    if '__attribute__' in message:
        return 'attribute or pragma', None, line_no, line_text
    return 'other (c2m parser)', None, line_no, line_text


def first_error(text, limit=900):
    lines = [line for line in (text or '').splitlines() if line.strip()]
    chosen = [line for line in lines if any(word in line.lower() for word in
                                            ('error', 'can not', 'excess', 'unfinished'))] or lines
    return '\n'.join(chosen[:5])[:limit]


def case_for_task(task, work):
    case = tp.rt.make_case(task, False, work)
    return dict(name=case['name'], stdin=case['stdin'], path=case['path'], args=case['args'])


def compare_outputs(left, right):
    return (left['stdout'] == right['stdout'] and left['stderr'] == right['stderr']
            and left['exit'] == right['exit'])


def measure(source, name, kind, case, root, gcc, mir, m2b, runs):
    generated = tp.generate_c(source, 'python' if source.suffix == '.py' else None, root, gcc)
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
    timeout = CASE_TIMEOUT if kind == 'compare' else CORPUS_TIMEOUT
    gcc_build = tp.timed_build(
        lambda: tp.build_commands(generated['shape'], generated['flags'], generated['libs'],
                                  generated['c_files'], '-O2', work / ('gcc-%d' % time.time_ns()),
                                  gcc, None), runs)
    gcc_run = None
    if gcc_build['ok']:
        reference_cmd = [str(gcc_build['binary']), *case.get('args', [])]
        gcc_run = run_repeated(lambda i: reference_cmd, work, case['path'] if case.get('stdin') else None,
                               timeout, runs)
    c2m_build = timed_c2m_build(generated['c_files'], generated['flags'], work, mir / 'c2m', m2b, runs)
    c2m_run, c2m_eg = None, None
    if c2m_build['ok'] and gcc_run and not gcc_run['timeout']:
        # argv[0] is the gcc binary path so the two runs see the same value; mir-bin-run takes
        # <bmir> <argv0> [args...].
        def c2m_command(_i):
            return [str(mir / 'mir-bin-run'), str(c2m_build['binary']),
                    str(gcc_build['binary']), *case.get('args', [])]
        c2m_run = run_repeated(c2m_command, work,
                               case['path'] if case.get('stdin') else None, timeout, runs)
        eg_command = [str(mir / 'c2m'), '-O2', *c2m_flags(generated['flags']),
                      *[str(p) for p in generated['c_files']], '-eg', *case.get('args', [])]
        c2m_eg = run_cmd(eg_command, work, case['path'] if case.get('stdin') else None, timeout)
        c2m_eg.pop('stdout_path', None)
        c2m_eg.pop('stderr_path', None)

    record['builds'] = dict(
        gcc_O2=dict(ok=gcc_build['ok'], seconds=gcc_build['seconds'], runs=gcc_build['runs']),
        c2m=dict(ok=c2m_build['ok'], seconds=c2m_build['seconds'], runs=c2m_build['runs']))
    record['runs'] = dict(
        gcc_O2=_run_summary(gcc_run), c2m=_run_summary(c2m_run), c2m_eg=_run_summary(c2m_eg))
    record['gcc_error'] = first_error(gcc_build['stderr']) if not gcc_build['ok'] else ''
    record['c2m_error'] = first_error(c2m_build['stderr'])
    if not c2m_build['ok']:
        bucket, construct, line_no, line_text = c2m_diagnose(c2m_build['stderr'], generated['c_files'])
        record['c2m_bucket'] = bucket
        record['c2m_construct'] = construct
        record['c2m_error_line'] = line_no
        record['c2m_error_line_text'] = (line_text or '')[:400]
        record['c2m_matches_gcc_o2'] = False
    else:
        matches = bool(gcc_run and not gcc_run['timeout'] and c2m_run and not c2m_run['timeout']
                       and compare_outputs(c2m_run, gcc_run))
        eg_matches = bool(c2m_eg and not c2m_eg['timeout'] and compare_outputs(c2m_eg, gcc_run))
        record['c2m_matches_gcc_o2'] = matches
        record['c2m_eg_matches_gcc_o2'] = eg_matches
        record['c2m_bucket'] = None if matches and eg_matches else 'wrong output'
        record['c2m_construct'] = None
        if record['c2m_bucket']:
            record['c2m_eg_diff'] = diff_excerpts(gcc_run, c2m_eg)
            record['c2m_run_diff'] = diff_excerpts(gcc_run, c2m_run)
    record['gcc_o2_deterministic'] = gcc_run.get('deterministic') if gcc_run else None
    record['c2m_deterministic'] = c2m_run.get('deterministic') if c2m_run else None
    shutil.rmtree(generated['work'], ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    return record


def _run_summary(result):
    if result is None:
        return dict(seconds=None, cpu=None, runs=[], timeout=None, exit=None, deterministic=None)
    return dict(seconds=result.get('wall'), cpu=result.get('cpu'), runs=result.get('runs', []),
                timeout=result.get('timeout'), exit=result.get('exit'),
                deterministic=result.get('deterministic'))


def diff_excerpts(reference, other):
    if other is None:
        return dict(reference=None, other=None)
    return dict(reference=dict(exit=reference['exit'],
                               stdout=reference['stdout'][:600].decode('utf-8', 'replace'),
                               stderr=reference['stderr'][:600].decode('utf-8', 'replace')),
                other=dict(exit=other.get('exit'),
                           timeout=other.get('timeout'),
                           stdout=(other.get('stdout') or b'')[:600].decode('utf-8', 'replace'),
                           stderr=(other.get('stderr') or b'')[:600].decode('utf-8', 'replace')))


EMITTER = {
    '_Generic inside __typeof__ (ail_len_t typedef)':
        'AIL_CURRENT/python/pkg-v12/cruntime.py:199-200 '
        '(typedef __typeof__(_Generic(...)) ail_len_t;)',
    '__int128': 'AIL_CURRENT/python/pkg-v12/cruntime.py:16893 (__int128 nn = (__int128)n; range slice)',
    '__uint128_t': 'AIL_CURRENT/python/pkg-v12/cruntime.py:3841-3844 (128-bit shift helper)',
    '__builtin_unreachable': 'AIL_CURRENT/python/pkg-v12/cruntime.py:433,4044,4065',
    '__asm__': 'AIL_CURRENT/python/pkg-v12/cruntime.py:365,30715; safetyrt.py:1437',
    'unsized struct-array compound literal from runtime values':
        'AIL_CURRENT/python/pkg-v12/pyfunc.py:24481',
}


def write_excerpts(result, directory):
    directory.mkdir(parents=True, exist_ok=True)
    seen = {}
    for record in result['programs'] + result.get('skipped', []):
        bucket = record.get('c2m_bucket')
        if not bucket or bucket == 'wrong output':
            continue
        seen.setdefault((bucket, record.get('c2m_construct') or ''), record)
    short = {'_Generic inside __typeof__ (ail_len_t typedef)': 'generic_in_typeof',
             '__int128': 'int128', '__uint128_t': 'uint128'}
    for number, ((bucket, construct), record) in enumerate(sorted(seen.items()), 1):
        slug = short.get(construct) or re.sub(
            r'[^a-z0-9]+', '_', (bucket + '_' + construct).lower()).strip('_')[:40]
        text = [
            'program: %s (%s)' % (record.get('source'), record.get('kind')),
            'bucket: %s' % bucket,
            'construct: %s' % (construct or '(see the C line)'),
            'c2m stderr:',
            *('  ' + line for line in (record.get('c2m_error') or '').splitlines()[:8]),
            'generated C line %s: %s' % (record.get('c2m_error_line'), record.get('c2m_error_line_text')),
            'emitted by: %s' % (EMITTER.get(construct, '(see the C line above)')),
        ]
        (directory / ('fail_%d_%s.txt' % (number, slug))).write_text('\n'.join(text) + '\n', encoding='utf-8')


def write_wrong(result, directory):
    for record in result['programs']:
        if record.get('c2m_bucket') != 'wrong output':
            continue
        slug = re.sub(r'[^A-Za-z0-9_.-]', '_', record['name'])
        lines = ['program: %s (%s)' % (record['source'], record['kind'])]
        for label, key in (('c2m -eg', 'c2m_eg_diff'), ('c2m mir-bin-run', 'c2m_run_diff')):
            diff = record.get(key) or {}
            lines.append('--- %s ---' % label)
            lines.append('gcc -O2 : exit=%s stdout=%r stderr=%r' % (
                (diff.get('reference') or {}).get('exit'),
                (diff.get('reference') or {}).get('stdout'),
                (diff.get('reference') or {}).get('stderr')))
            lines.append('%s : exit=%s stdout=%r stderr=%r timeout=%s' % (
                label, (diff.get('other') or {}).get('exit'),
                (diff.get('other') or {}).get('stdout'),
                (diff.get('other') or {}).get('stderr'),
                (diff.get('other') or {}).get('timeout')))
        (directory / ('wrong_%s.txt' % slug)).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def summarize(result):
    programs = result['programs']
    generated = [p for p in programs if p.get('c_files')]
    baseline = [p for p in generated if p.get('builds', {}).get('gcc_O2', {}).get('ok')]
    built = [p for p in baseline if p.get('builds', {}).get('c2m', {}).get('ok')]
    matches = [p for p in built if p.get('c2m_matches_gcc_o2')]
    buckets, constructs = {}, {}
    for p in programs:
        key = p.get('c2m_bucket')
        if key:
            buckets[key] = buckets.get(key, 0) + 1
            construct = p.get('c2m_construct') or (p.get('c2m_error_line_text') or '')[:90]
            if construct:
                constructs[construct] = constructs.get(construct, 0) + 1

    def med_build(label):
        return median([p['builds'][label]['seconds'] for p in programs
                       if p.get('builds', {}).get(label, {}).get('ok')])

    def med_metric(label, key):
        return median([p['runs'][label][key] for p in programs
                       if p.get('runs', {}).get(label, {}).get(key) is not None])

    kinds = {}
    for kind in ('compare', 'corpus'):
        subset = [p for p in programs if p.get('kind') == kind]
        kinds[kind] = dict(attempted=len(subset),
                           gcc_o2_built=sum(1 for p in subset if p.get('builds', {}).get('gcc_O2', {}).get('ok')),
                           c2m_built=sum(1 for p in subset if p.get('builds', {}).get('c2m', {}).get('ok')),
                           c2m_matches=sum(1 for p in subset if p.get('c2m_matches_gcc_o2')))
    return dict(
        attempted=len(programs), c_generated=len(generated), gcc_o2_built=len(baseline),
        c2m_built=len(built), c2m_matches=len(matches),
        c2m_build_failures=len(baseline) - len(built), wrong_output=len(built) - len(matches),
        buckets=buckets, constructs=constructs, kinds=kinds,
        corpus_programs=[p['name'] for p in programs if p.get('kind') == 'corpus'],
        median_c_build_s=dict(gcc_O2=med_build('gcc_O2'), c2m=med_build('c2m')),
        median_run_s=dict(gcc_O2=med_metric('gcc_O2', 'seconds'), c2m=med_metric('c2m', 'seconds'),
                          c2m_eg=med_metric('c2m_eg', 'seconds')),
        median_run_cpu_s=dict(gcc_O2=med_metric('gcc_O2', 'cpu'), c2m=med_metric('c2m', 'cpu')))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mir', default=os.environ.get('AIL_MIR_C2M') or os.path.expanduser('~/scratch/mir'))
    parser.add_argument('--gcc', default=shutil.which('gcc'))
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--corpus', type=int, default=40)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--out', default='/tmp/devcc.json')
    parser.add_argument('--excerpts', help='directory for fail_*.txt excerpts')
    parser.add_argument('--from-json', help='re-print the summary of an existing result file')
    parser.add_argument('--only', choices=('compare', 'corpus'))
    args = parser.parse_args()
    if args.from_json:
        result = json.loads(pathlib.Path(args.from_json).read_text(encoding='utf-8'))
        for record in result['programs'] + result.get('skipped', []):
            if record.get('c2m_bucket') and record['c2m_bucket'] != 'wrong output':
                text = (record.get('c2m_error_line_text') or '').lower()
                if '__uint128_t' in text:
                    record['c2m_bucket'], record['c2m_construct'] = 'unsupported builtin or intrinsic', '__uint128_t'
                elif '__int128' in text:
                    record['c2m_bucket'], record['c2m_construct'] = 'unsupported builtin or intrinsic', '__int128'
                elif '_generic' in text:
                    record['c2m_bucket'] = 'other (c2m parser)'
                    record['c2m_construct'] = '_Generic inside __typeof__ (ail_len_t typedef)'
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
            write_wrong(result, pathlib.Path(args.excerpts))
        print(json.dumps(summarize(result), indent=1))
        return 0
    mir = pathlib.Path(args.mir).resolve()
    c2m, mirbinrun, m2b = mir / 'c2m', mir / 'mir-bin-run', mir / 'm2b'
    for tool in (c2m, mirbinrun, m2b):
        if not tool.is_file():
            parser.error('missing %s (build MIR first: make in ~/scratch/mir)' % tool)
    gcc = args.gcc
    if not gcc:
        parser.error('gcc is required')
    version = subprocess.run([str(c2m), '-h'], capture_output=True, text=True)
    version_text = ((version.stdout or '') + (version.stderr or '')).strip().splitlines()
    c2m_version = next((line for line in version_text if 'version' in line.lower()), '')
    gcc_version = subprocess.run([gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    root = pathlib.Path(tempfile.mkdtemp(prefix='devcc-'))
    result = dict(meta=dict(
        date=time.strftime('%Y-%m-%d'), seed=args.seed, runs=args.runs,
        c2m=c2m_version, c2m_path=str(c2m),
        mir_release=subprocess.run(['git', '-C', str(mir), 'describe', '--tags'], capture_output=True,
                                   text=True).stdout.strip(),
        mir_commit=subprocess.run(['git', '-C', str(mir), 'rev-parse', 'HEAD'], capture_output=True,
                                  text=True).stdout.strip(),
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
                                 root, gcc, mir, m2b, args.runs)
                result['programs'].append(record)
                print('   ail=%s c2m_build=%s match=%s bucket=%s' % (
                    record['ail_ok'], record.get('builds', {}).get('c2m', {}).get('ok'),
                    record.get('c2m_matches_gcc_o2'), record.get('c2m_bucket')), file=sys.stderr, flush=True)
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
                                 root, gcc, mir, m2b, args.runs)
                if record.get('ail_ok') and record.get('builds', {}).get('gcc_O2', {}).get('ok'):
                    chosen.append(record['name'])
                    result['programs'].append(record)
                    print('   c2m_build=%s match=%s bucket=%s' % (
                        record.get('builds', {}).get('c2m', {}).get('ok'),
                        record.get('c2m_matches_gcc_o2'), record.get('c2m_bucket')), file=sys.stderr, flush=True)
                else:
                    record['skipped'] = 'AIL refused or gcc -O2 could not build the emitted C'
                    result.setdefault('skipped', []).append(record)
                    print('   skipped:', record.get('status') or record.get('gcc_error') or '', file=sys.stderr, flush=True)
                pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
            result['meta']['corpus_candidates_tried'] = tried
    finally:
        summary = summarize(result)
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(summary, indent=1))
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
            write_wrong(result, pathlib.Path(args.excerpts))
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
