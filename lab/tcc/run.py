#!/usr/bin/env python3
"""Quick-run probe: compile AIL's generated C with TinyCC instead of gcc -O2.

    python3 lab/tcc/run.py --out /tmp/tcc.json --excerpts lab/tcc

For the ten `lab/compare/src/<task>/main.py` programs and fifty `corpus/gdev`
programs this generates the C once through `ail_chatgpt.py compile --debug-dir`
(which writes the exact translation unit the compiler saw and the recorded
compiler command line), then:

  * censuses the C against five compilers/variants, recording the first error
    and the construct that caused it (tcc 0.9.27 from apt, tcc 0.9.28rc from
    upstream, and 0.9.28rc + lab/tcc/tcc_prelude.h);
  * times three cold builds (median of 3) of gcc -O2, gcc -O0 and
    tcc 0.9.28rc+prelude on the same C, and runs each binary three times on
    the task's first public case (or no input for a corpus program);
  * compares stdout, stderr and exit status byte-for-byte with the gcc -O2 build;
  * measures the edit-run loop: a full cold `ail compile` + run of the small
    input with PIPE_CC=gcc versus PIPE_CC=tcc+prelude, and the same build warm
    from the existing AIL_CACHE when the build cache has the result.

Nothing in the compiler, runtime or default build is changed: tcc is only ever
invoked by this measurement, through PIPE_CC or directly on the saved C.
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
WRAPPER = HERE / 'cc_tcc.py'
PRELUDE = HERE / 'tcc_prelude.h'
EXACT_INT = ('chain_relax', 'rail_transfer')
CASE_TIMEOUT = 120
CORPUS_TIMEOUT = 30
SEED = 20261106

sys.path.insert(0, str(COMPARE))
import run_task as rt  # noqa: E402


def median(values, digits=4):
    return round(statistics.median(values), digits) if values else None


def first_error(text, limit=600):
    lines = [line for line in (text or '').splitlines() if line.strip()]
    chosen = [line for line in lines if 'error' in line.lower()][:3] or lines[:3]
    return '\n'.join(chosen)[:limit]


def c_line(path, number):
    try:
        lines = pathlib.Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return None
    return lines[number - 1].strip() if 1 <= number <= len(lines) else None


def _flags_before(body, cut):
    flags, i = [], 0
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
    libs, i = [], last_input + 1
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


def generate_c(source, syntax, exact, root, gcc):
    digest = hashlib.sha1(str(source).encode()).hexdigest()[:8]
    name = re.sub(r'[^A-Za-z0-9_]', '_', source.parent.name if source.parent != CORPUS else source.stem)
    work = root / ('gen-' + name + '-' + digest)
    shutil.rmtree(work, ignore_errors=True)
    for sub in ('cache', 'tmp'):
        (work / sub).mkdir(parents=True)
    dbg, out = work / 'dbg', work / 'ail-prog'
    command = [sys.executable, '-B', str(AIL), 'compile', str(source), '-o', str(out), '--debug-dir', str(dbg)]
    if syntax:
        command += ['--syntax', 'python']
    if exact:
        command += ['--exact-int']
    env = dict(os.environ, AIL_CACHE=str(work / 'cache'), TMPDIR=str(work / 'tmp'),
               PIPE_CC=gcc, AIL_NO_CACHE='1', AIL_SERVER='0', PYTHONUTF8='1')
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    start = time.perf_counter()
    done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    result = dict(ok=done.returncode == 0, wall=wall, stderr=(done.stderr or done.stdout)[-1600:],
                  work=work, c_files=[], shape='single', flags=[], libs=[])
    report_path = dbg / 'native_report.json'
    if report_path.is_file():
        try:
            result.update(parse_report(json.loads(report_path.read_text(encoding='utf-8')), dbg))
        except ValueError:
            pass
    if not result['c_files']:
        result['c_files'] = sorted(str(p) for p in dbg.glob('*.c'))
    result['c_files'] = [pathlib.Path(p) for p in result['c_files']]
    return result


# --- tcc failure classification -------------------------------------------------------------

def index_too_large_construct(line_text):
    text = line_text or ''
    if re.search(r'\(\s*(?:struct\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\[\s*\]\s*\)\s*\{', text):
        return 'unsized struct-array compound literal from runtime values'
    if re.search(r'\b[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\s*\[\s*\]\s*=\s*\{', text):
        return 'unsized struct-array variable declaration from runtime values'
    return 'index too large (see the C line)'


def classify(lowered, line_text):
    haystack = (line_text or '').lower() + '\n' + lowered
    if '__int128' in haystack or 'int128' in haystack:
        return 'int128', '__int128 (no 128-bit integer type in tcc)'
    if '__builtin' in haystack or re.search(r'builtin_[a-z_]+', haystack):
        return 'builtin', 'unsupported __builtin_*'
    if re.search(r'\basm\b|__asm', haystack) or 'inline assembly' in haystack:
        return 'inline asm', 'inline assembly'
    if '_thread_local' in haystack or '__thread' in haystack:
        return 'attribute/pragma', 'C11 _Thread_local storage class'
    if 'vector_size' in haystack or 'may_alias' in haystack or 'target(' in haystack:
        return 'vector extension', 'GCC vector extension'
    if '__attribute__' in haystack or '#pragma' in haystack or 'attribute' in haystack:
        return 'attribute/pragma', '__attribute__ / #pragma'
    if 'statement expression' in haystack or re.search(r'\(\s*\{', line_text or ''):
        return 'statement expression', 'statement expression ({ ... })'
    if 'index too large' in lowered:
        return 'unsized aggregate', index_too_large_construct(line_text)
    if any(word in lowered for word in ('undefined symbol', 'unresolved', 'undefined reference',
                                        'cannot find', 'file not found', 'relocation')):
        return 'link error', 'link error'
    if 'warning: implicit declaration' in lowered and line_text is None:
        return 'builtin', 'tcc does not implement the builtin'
    return 'other (tcc parser)', None


def diagnose(stderr, c_files):
    text = stderr or ''
    line_no = line_text = None
    match = re.search(r'(\S+\.c):(\d+):\s*(?:error|warning)', text)
    if match:
        line_no = int(match.group(2))
        named = pathlib.Path(match.group(1)).name
        ordered = ([p for p in c_files if pathlib.Path(p).name == named]
                   + [p for p in c_files if pathlib.Path(p).name != named])
        for c_file in ordered:
            found = c_line(c_file, line_no)
            if found:
                line_text = found
                break
    bucket, construct = classify(text.lower(), line_text)
    return bucket, construct, line_no, line_text


# --- builds ---------------------------------------------------------------------------------

TCC_LABELS = ('tcc-apt', 'tcc-upstream', 'tcc-prelude')


def c_flags(label, flags):
    if label in TCC_LABELS:
        return [f for f in flags if f.startswith(('-I', '-D', '-U', '-L', '-l', '-O', '-g', '-std='))
                or f in ('-pthread', '-static')]
    if label == 'gcc-O0':
        replaced = ['-O0' if f == '-O2' else f for f in flags]
        if '-O0' not in replaced:
            replaced.insert(0, '-O0')
        return replaced
    return list(flags)


def prepare_sources(sources, label, work):
    """For the prelude variant, write a patched copy once (outside the timed region)."""
    if label != 'tcc-prelude':
        return sources
    patched_dir = work / 'patched'
    patched_dir.mkdir(exist_ok=True)
    prelude = PRELUDE.read_text(encoding='utf-8')
    result = []
    for source in sources:
        target = patched_dir / (pathlib.Path(source).name + '.tcc.c')
        target.write_text(prelude + pathlib.Path(source).read_text(encoding='utf-8', errors='replace'),
                          encoding='utf-8', errors='replace')
        result.append(target)
    return result


def build_commands(shape, flags, libs, sources, label, attempt, gcc, tcc_apt, tcc_upstream):
    attempt.mkdir(parents=True, exist_ok=True)
    if label == 'tcc-apt':
        cc = str(tcc_apt)
    elif label.startswith('tcc'):
        cc = str(tcc_upstream)
    else:
        cc = gcc
    flags = c_flags(label, flags)
    binary = attempt / 'prog'
    if shape == 'single' or len(sources) == 1:
        return [[cc, *flags, str(sources[0]), *libs, '-o', str(binary)]]
    commands, objects = [], []
    for i, source in enumerate(sources):
        obj = attempt / ('u%d.o' % i)
        objects.append(obj)
        commands.append([cc, *flags, '-c', str(source), '-o', str(obj)])
    commands.append([cc, *flags, '-o', str(binary), *[str(o) for o in objects], *libs])
    return commands


def timed_build(make_commands, runs):
    walls, errors, binary = [], [], None
    for _ in range(runs):
        commands = make_commands()
        start = time.perf_counter()
        for command in commands:
            done = subprocess.run(command, capture_output=True, text=True)
            if done.returncode:
                errors.append((done.stderr or done.stdout)[-1600:])
                break
        walls.append(time.perf_counter() - start)
        if errors:
            break
        binary = pathlib.Path(commands[-1][commands[-1].index('-o') + 1])
    return dict(ok=not errors and binary is not None and binary.is_file(),
                seconds=median(walls), runs=[round(w, 4) for w in walls],
                stderr=errors[0] if errors else '', binary=binary)


def run_binary(binary, case, work, tag, runs, timeout):
    walls, outs, errs, codes = [], [], [], []
    for i in range(runs):
        stdout_path, stderr_path = work / ('%s-%d.out' % (tag, i)), work / ('%s-%d.err' % (tag, i))
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


# --- full AIL builds (edit-run loop) --------------------------------------------------------

def ail_build(source, syntax, exact, label, cache_dir, work, gcc, tcc_upstream):
    WRAPPER.chmod(0o755)
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'prog'
    command = [sys.executable, '-B', str(AIL), 'compile', str(source), '-o', str(out)]
    if syntax:
        command += ['--syntax', 'python']
    if exact:
        command += ['--exact-int']
    env = dict(os.environ, AIL_CACHE=str(cache_dir), TMPDIR=str(work / 'tmp'),
               AIL_SERVER='0', PYTHONUTF8='1')
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    if label == 'tcc':
        env.update(PIPE_CC=str(WRAPPER), TCC_BIN=str(tcc_upstream), TCC_PRELUDE=str(PRELUDE))
    else:
        env.pop('PIPE_CC', None)
    (work / 'tmp').mkdir(exist_ok=True)
    start = time.perf_counter()
    done = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=1800)
    wall = time.perf_counter() - start
    return dict(ok=done.returncode == 0 and out.is_file(), wall=wall, out=out,
                stderr=first_error(done.stderr or done.stdout))


# --- one program ----------------------------------------------------------------------------

def measure(source, name, kind, case, exact, root, gcc, tcc_apt, tcc_upstream, runs, ail_state=None):
    generated = generate_c(source, source.suffix == '.py', exact, root, gcc)
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
    sources = {}
    for label in ('gcc-O2', 'gcc-O0', *TCC_LABELS):
        sources[label] = prepare_sources(generated['c_files'], label, work)
    builds = {}
    for label in ('gcc-O2', 'gcc-O0', 'tcc-prelude'):
        counter = {'n': 0}

        def commands_for(label=label, counter=counter):
            counter['n'] += 1
            return build_commands(generated['shape'], generated['flags'], generated['libs'],
                                  sources[label], label, work / ('build-' + label + '-%d' % counter['n']),
                                  gcc, tcc_apt, tcc_upstream)

        builds[label] = timed_build(commands_for, runs)
    for label in ('tcc-apt', 'tcc-upstream'):
        builds[label] = timed_build(lambda label=label: build_commands(
            generated['shape'], generated['flags'], generated['libs'], sources[label], label,
            work / ('build-' + label + '-1'), gcc, tcc_apt, tcc_upstream), 1)

    run_case = dict(case)
    timeout = CASE_TIMEOUT if kind == 'compare' else CORPUS_TIMEOUT
    records = {}
    for label in ('gcc-O2', 'gcc-O0', 'tcc-prelude', 'tcc-apt', 'tcc-upstream'):
        build = builds[label]
        entry = dict(build_ok=build['ok'], build_s=build['seconds'], build_runs=build['runs'])
        if build['ok']:
            entry.update(run_binary(build['binary'], run_case, work, 'run-' + label, runs, timeout))
        else:
            entry['build_error'] = first_error(build['stderr'])
        records[label] = entry
    reference = records['gcc-O2']
    for label, entry in records.items():
        if label == 'gcc-O2':
            continue
        entry['match'] = bool(reference.get('build_ok') and not reference.get('timeout')
                              and entry.get('build_ok') and not entry.get('timeout')
                              and entry.get('stdout') == reference.get('stdout')
                              and entry.get('stderr') == reference.get('stderr')
                              and entry.get('exit') == reference.get('exit'))
    record['builds'] = {label: dict(ok=records[label]['build_ok'], seconds=records[label]['build_s'],
                                    runs=records[label]['build_runs']) for label in records}
    record['runs'] = {}
    for label, entry in records.items():
        row = {key: entry.get(key) for key in ('seconds', 'runs', 'timeout', 'deterministic', 'match', 'exit')}
        if entry.get('stdout') is not None:
            row['stdout_sha'] = hashlib.sha256(entry['stdout']).hexdigest()[:16]
            row['stderr_sha'] = hashlib.sha256(entry['stderr']).hexdigest()[:16]
        record['runs'][label] = row
    for label in ('tcc-apt', 'tcc-upstream', 'tcc-prelude'):
        entry = records[label]
        if not entry['build_ok']:
            bucket, construct, line_no, line_text = diagnose(entry.get('build_error', ''), sources[label])
            entry['bucket'], entry['construct'] = bucket, construct
            entry['error_line'], entry['error_line_text'] = line_no, (line_text or '')[:400]
        elif not entry.get('match'):
            entry['bucket'] = 'wrong output'
        record['census'] = {label: dict(ok=records[label]['build_ok'],
                                        bucket=records[label].get('bucket'),
                                        construct=records[label].get('construct'),
                                        error=first_error(records[label].get('build_error', '')),
                                        error_line=records[label].get('error_line'),
                                        error_line_text=records[label].get('error_line_text')) for label in TCC_LABELS}
    record['census']['gcc-O0'] = dict(ok=records['gcc-O0']['build_ok'])

    # Full AIL builds (the edit-run loop) only where tcc builds the same C, so the
    # comparison is real; corpus builds are capped by --ail-limit.
    record['ail'] = {}
    tcc_ok = records['tcc-prelude']['build_ok']
    do_ail = bool(ail_state) and tcc_ok and (kind == 'compare' or ail_state['done'] < ail_state['limit'])
    if not do_ail:
        record['ail_skipped'] = ('tcc did not build the C' if not tcc_ok else 'corpus AIL-build budget reached')
    else:
        ail_runs = ail_state.get('runs', runs)
        for label in ('gcc', 'tcc'):
            cold_walls, warm_walls, cold_binaries = [], [], []
            for rep in range(ail_runs):
                cache = work / ('ailcache-%s-cold%d' % (label, rep))
                cold = ail_build(source, source.suffix == '.py', exact, label, cache, work / ('ail-%s-cold%d' % (label, rep)),
                                 gcc, tcc_upstream)
                cold_walls.append(cold['wall'])
                cold_binaries.append(cold)
            warm_cache = work / ('ailcache-%s-warm' % label)
            warm_dir = work / ('ail-%s-warm' % label)
            first = ail_build(source, source.suffix == '.py', exact, label, warm_cache, warm_dir,
                              gcc, tcc_upstream)
            warm_walls.append(first['wall'])
            for rep in range(1, ail_runs):
                warm = ail_build(source, source.suffix == '.py', exact, label, warm_cache, warm_dir,
                                 gcc, tcc_upstream)
                warm_walls.append(warm['wall'])
            entry = dict(cold_s=median(cold_walls), cold_runs=[round(w, 4) for w in cold_walls],
                         warm_s=median(warm_walls[1:] or warm_walls), warm_runs=[round(w, 4) for w in warm_walls],
                         ok=all(b['ok'] for b in cold_binaries) and first['ok'],
                         error=next((b['stderr'] for b in cold_binaries if not b['ok']), None))
            good = next((b for b in cold_binaries if b['ok']), None)
            if good:
                run = run_binary(good['out'], run_case, work, 'ail-run-' + label, runs, timeout)
                entry.update(run_s=run.get('seconds'), run_runs=run.get('runs'),
                             run_timeout=run.get('timeout'), exit=run.get('exit'))
                if run.get('stdout') is not None:
                    entry['stdout_sha'] = hashlib.sha256(run['stdout']).hexdigest()[:16]
                    entry['edit_run_s'] = round(entry['cold_s'] + run['seconds'], 4)
            record['ail'][label] = entry
        if record['ail']['gcc'].get('stdout_sha') and record['ail']['tcc'].get('stdout_sha'):
            record['ail']['match'] = record['ail']['gcc']['stdout_sha'] == record['ail']['tcc']['stdout_sha']
        if kind != 'compare':
            ail_state['done'] += 1
    shutil.rmtree(generated['work'], ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    return record


def case_for(name, kind, work):
    if kind == 'compare':
        case = rt.make_case(name, True, work)       # first public (small) example
        return dict(name=case['name'], stdin=case['stdin'], path=case['path'], args=case['args'])
    return dict(name='no-input', stdin=False, path=None, args=[])


CONSTRUCT_EMITTER = {
    'C11 _Thread_local storage class': 'cruntime.py:17245-17246 (ail__rep_stk / ail__rep_n), jsonrt.py:858',
    'unsized struct-array compound literal from runtime values': 'pyfunc.py:24481 (ail_stdout_parts)',
    'unsized struct-array variable declaration from runtime values': 'cruntime.py:6450,6508,6538 (bytes replace/translate)',
    '__int128 (no 128-bit integer type in tcc)': 'cruntime.py:29709 (ail_rand_floordiv), general slice and pow paths',
    'unsupported __builtin_*': 'cruntime.py:433,4044,4065 (__builtin_unreachable); bigint_obj.py:403-411 (__builtin_*_overflow)',
}


def write_excerpts(result, directory):
    directory.mkdir(parents=True, exist_ok=True)
    seen = {}
    for record in result['programs'] + result.get('skipped', []):
        for label, row in (record.get('census') or {}).items():
            if label == 'gcc-O0' or row.get('ok') or not row.get('bucket'):
                continue
            seen.setdefault((label, row['bucket'], row.get('construct') or ''), (record, row))
    for number, ((label, bucket, construct), (record, row)) in enumerate(sorted(seen.items()), 1):
        slug = re.sub(r'[^a-z0-9]+', '_', (label + '_' + bucket).lower()).strip('_')[:44]
        lines = [
            'variant: %s' % label,
            'program: %s (%s)' % (record.get('source'), record.get('kind')),
            'bucket: %s' % bucket,
            'construct: %s' % (construct or '(see the C line)'),
            'first error:',
            *('  ' + line for line in (row.get('error') or '').splitlines()[:8]),
            'generated C line %s: %s' % (row.get('error_line'), row.get('error_line_text')),
            'emitted by: %s' % (CONSTRUCT_EMITTER.get(construct) or CONSTRUCT_EMITTER.get(bucket) or '(see the C line)'),
        ]
        (directory / ('fail_%d_%s.txt' % (number, slug))).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def summarize(result):
    programs = result['programs']
    out = dict(attempted=len(programs), skipped=len(result.get('skipped', [])))
    for kind in ('compare', 'corpus'):
        subset = [p for p in programs if p.get('kind') == kind]
        out[kind] = dict(programs=len(subset),
                         gcc_o2=sum(1 for p in subset if p['builds']['gcc-O2']['ok']),
                         gcc_o0=sum(1 for p in subset if p['builds']['gcc-O0']['ok']),
                         tcc_apt=sum(1 for p in subset if p['census']['tcc-apt']['ok']),
                         tcc_upstream=sum(1 for p in subset if p['census']['tcc-upstream']['ok']),
                         tcc_prelude=sum(1 for p in subset if p['census']['tcc-prelude']['ok']),
                         tcc_match=sum(1 for p in subset if p['census']['tcc-prelude'].get('ok')
                                       and p['runs']['tcc-prelude'].get('match')))
    buckets = {}
    for p in programs:
        for label in TCC_LABELS:
            row = p['census'][label]
            if not row['ok'] and row.get('bucket'):
                key = (label, row['bucket'], row.get('construct') or '')
                buckets[key] = buckets.get(key, 0) + 1
    out['buckets'] = [dict(variant=v, bucket=b, construct=c, count=n)
                      for (v, b, c), n in sorted(buckets.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1]))]
    for label in ('gcc-O2', 'gcc-O0', 'tcc-prelude'):
        out['median_build_s_' + label] = median([p['builds'][label]['seconds'] for p in programs
                                                if p['builds'][label]['ok']])
    out['median_run_s_tcc-prelude'] = median([p['runs']['tcc-prelude']['seconds'] for p in programs
                                             if p['runs']['tcc-prelude'].get('seconds') is not None])
    out['median_run_s_gcc-O2'] = median([p['runs']['gcc-O2']['seconds'] for p in programs
                                        if p['runs']['gcc-O2'].get('seconds') is not None])
    for label in ('gcc', 'tcc'):
        rows = [p.get('ail', {}).get(label, {}) for p in programs]
        out['median_ail_cold_s_' + label] = median([r['cold_s'] for r in rows if r.get('ok')])
        out['median_ail_warm_s_' + label] = median([r['warm_s'] for r in rows if r.get('ok')])
        out['median_edit_run_s_' + label] = median([r['edit_run_s'] for r in rows
                                                   if r.get('edit_run_s') is not None])
    built = [p for p in programs if p['census']['tcc-prelude']['ok']]
    out['tcc_built_programs'] = [p['name'] for p in built]
    out['tcc_wrong_output'] = [p['name'] for p in built if not p['runs']['tcc-prelude'].get('match')]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tcc-apt', default='/usr/bin/tcc')
    parser.add_argument('--tcc-upstream', default='/tmp/tcc-install/bin/tcc')
    parser.add_argument('--gcc', default=shutil.which('gcc'))
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--corpus', type=int, default=50)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--ail-runs', type=int, default=2, help='cold/warm repetitions of the full AIL build')
    parser.add_argument('--ail-limit', type=int, default=12, help='corpus programs with a full AIL build measurement')
    parser.add_argument('--out', default='/tmp/tcc.json')
    parser.add_argument('--excerpts')
    parser.add_argument('--only', choices=('compare', 'corpus'))
    parser.add_argument('--from-json')
    args = parser.parse_args()
    if args.from_json:
        result = json.loads(pathlib.Path(args.from_json).read_text(encoding='utf-8'))
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
        print(json.dumps(summarize(result), indent=1))
        return 0
    tcc_apt, tcc_upstream = pathlib.Path(args.tcc_apt), pathlib.Path(args.tcc_upstream)
    for path in (tcc_apt, tcc_upstream):
        if not path.is_file():
            parser.error('tcc not found at %s' % path)
    version = lambda path: subprocess.run([str(path), '-v'], capture_output=True, text=True)
    tcc_apt_version = ((version(tcc_apt).stdout or '') + (version(tcc_apt).stderr or '')).strip().splitlines()[0]
    tcc_upstream_version = ((version(tcc_upstream).stdout or '') + (version(tcc_upstream).stderr or '')).strip().splitlines()[0]
    WRAPPER.chmod(0o755)
    root = pathlib.Path(tempfile.mkdtemp(prefix='tccquick-'))
    ail_state = dict(limit=args.ail_limit, runs=args.ail_runs, done=0)
    result = dict(meta=dict(date=time.strftime('%Y-%m-%d'), seed=args.seed, runs=args.runs,
                            ail_runs=args.ail_runs, ail_limit=args.ail_limit,
                            tcc_apt=tcc_apt_version, tcc_upstream=tcc_upstream_version,
                            gcc=subprocess.run([args.gcc, '--version'], capture_output=True, text=True).stdout.splitlines()[0],
                            python=sys.version.split()[0], cpus=os.cpu_count(), work=str(root)),
                  programs=[])
    try:
        if args.only != 'corpus':
            for task in sorted(p.name for p in (COMPARE / 'src').iterdir() if (p / 'main.py').is_file()):
                print('== compare', task, file=sys.stderr, flush=True)
                case_dir = root / ('case-' + task)
                case_dir.mkdir(parents=True, exist_ok=True)
                case = case_for(task, 'compare', case_dir)
                record = measure(COMPARE / 'src' / task / 'main.py', task, 'compare', case,
                                 task in EXACT_INT, root, args.gcc, tcc_apt, tcc_upstream, args.runs, ail_state)
                if record.get('ail_ok') and 'builds' in record:
                    result['programs'].append(record)
                else:
                    record['skipped'] = 'AIL refused the source'
                    result.setdefault('skipped', []).append(record)
                print('   gcc=%s tcc=%s bucket=%s' % (
                    record.get('builds', {}).get('gcc-O2', {}).get('ok'),
                    record.get('census', {}).get('tcc-prelude', {}).get('ok'),
                    record.get('census', {}).get('tcc-prelude', {}).get('bucket')), file=sys.stderr, flush=True)
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
                record = measure(source, source.stem, 'corpus', case_for(source.stem, 'corpus', root), False,
                                 root, args.gcc, tcc_apt, tcc_upstream, args.runs, ail_state)
                if record.get('ail_ok') and record.get('builds', {}).get('gcc-O2', {}).get('ok'):
                    chosen.append(record['name'])
                    result['programs'].append(record)
                    print('   tcc=%s bucket=%s' % (record['census']['tcc-prelude']['ok'],
                                                   record['census']['tcc-prelude'].get('bucket')), file=sys.stderr, flush=True)
                else:
                    record['skipped'] = 'AIL refused or gcc -O2 could not build the emitted C'
                    result.setdefault('skipped', []).append(record)
                    print('   skipped:', record.get('status') or record.get('census', {}).get('gcc-O2'), file=sys.stderr, flush=True)
                pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
            result['meta']['corpus_candidates_tried'] = tried
    finally:
        summary = summarize(result)
        pathlib.Path(args.out).write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        if args.excerpts:
            write_excerpts(result, pathlib.Path(args.excerpts))
        print(json.dumps(summary, indent=1))
        shutil.rmtree(root, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
