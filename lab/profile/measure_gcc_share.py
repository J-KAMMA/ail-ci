#!/usr/bin/env python3
"""Measure the share of gcc -O2 time a generated program spends on its runtime prelude.

For each sampled program in lab/corpus/programs the compiler runs once with --debug-dir,
which keeps the generated C.  The C is split at the first program function body reported by
native_report.json: everything before it is the runtime prelude (the includes, the
cruntime.emit pieces and the helper declarations), the rest is the program's own code.

gcc -c is timed (median of REPEAT runs) for:
  full     the whole generated C
  prelude  the prelude text alone, which compiles as its own translation unit
  empty    a trivial translation unit (the gcc startup floor)
and the reported share is (prelude - empty) / (full - empty), pooled over the sample by
summing the milliseconds so that a build's cost is weighted by its size.

    python3 lab/profile/measure_gcc_share.py [COUNT]

Writes the raw rows and summary to a temporary directory and prints them.
"""
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
CORPUS = ROOT / 'lab' / 'corpus' / 'programs'
REPEAT = 5
SEED = 20261028


def run_compile(source, work):
    work.mkdir(parents=True)
    prog = work / 'prog.ail'
    prog.write_bytes(source.read_bytes())
    debug = work / 'debug'
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, '-B', str(AIL), 'compile', str(prog), '--syntax', 'python',
         '-o', str(work / 'exe'), '--debug-dir', str(debug), '--json'],
        capture_output=True, text=True, env=env, timeout=300)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        try:
            message = json.loads(result.stdout)['message']
        except (ValueError, KeyError, TypeError):
            message = result.stdout or result.stderr
        return None, elapsed, (message or 'failed').strip().splitlines()[:1]
    report = json.loads((debug / 'native_report.json').read_text())
    generated = report['generated'][0]
    return (generated, Path(generated['debug_path']), report), elapsed, None


def split_generated(generated, text):
    """(prelude, program): the split before the first program function body."""
    starts = [f['c_start'] for f in generated['functions'] if f.get('mapped')]
    if starts:
        cut = min(starts)
        return text[:cut], text[cut:]
    # the report could not map a body: use the first non-static definition and its prototype
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = re.match(r'^[A-Za-z_][A-Za-z0-9_ \t\*]*\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{', line)
        if match and not line.startswith('static') and not line.startswith('typedef'):
            name = match.group(1)
            cut_line = index
            for back in range(index - 1, max(-1, index - 40), -1):
                if re.search(r'\b%s\s*\([^;]*\)\s*;' % re.escape(name), lines[back]):
                    cut_line = back
                    break
            cut = sum(len(item) for item in lines[:cut_line])
            return text[:cut], text[cut:]
    raise RuntimeError('no mapped function and no fallback split')


def compile_flags(report, c_name):
    """The compile flags the build actually passed, with the link step removed."""
    fallback = ['-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off', '-fopenmp-simd',
                '-fno-asynchronous-unwind-tables']
    for operation in reversed(report['operations']):
        args = [str(part) for part in operation.get('command') or []]
        if not any(Path(part).name == c_name for part in args):
            continue
        flags, skip = [], False
        for arg in args[1:]:
            if skip:
                skip = False
            elif arg == '-o':
                skip = True
            elif arg.startswith('-l') or arg in ('-pthread', '-static'):
                continue
            elif arg.endswith(('.c', '.o', '.a', '.so')):
                continue
            elif arg.startswith('-'):
                flags.append(arg)
        return flags or fallback
    return fallback


def median_ms(command):
    subprocess.run(command, capture_output=True, timeout=120)          # warm the file cache
    samples = []
    for _ in range(REPEAT):
        started = time.perf_counter()
        result = subprocess.run(command, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError('%s failed: %s' % (command, result.stderr[-300:]))
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples)


def candidates():
    sources = sorted(CORPUS.glob('*/*.py'))
    random.Random(SEED).shuffle(sources)
    return sources


def main():
    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    work_root = Path(tempfile.mkdtemp(prefix='gcc-share-'))
    empty = work_root / 'empty.c'
    empty.write_text('')
    rows, skipped, flags = [], [], None
    for index, source in enumerate(candidates()):
        if len(rows) >= wanted or index >= 3 * wanted:
            break
        work = work_root / ('p%02d' % index)
        try:
            data, seconds, error = run_compile(source, work)
        except subprocess.TimeoutExpired:
            skipped.append((str(source.relative_to(CORPUS)), 'compile timeout'))
            continue
        if data is None:
            skipped.append((str(source.relative_to(CORPUS)), (error or ['failed'])[-1]))
            continue
        generated, c_path, report = data
        text = c_path.read_text()
        prelude, _program = split_generated(generated, text)
        prelude_file = work / 'prelude.c'
        prelude_file.write_text(prelude)
        if flags is None:
            flags = compile_flags(report, c_path.name)
            empty_ms = median_ms(['cc', *flags, '-c', str(empty), '-o', str(work_root / 'empty.o')])
        try:
            full_ms = median_ms(['cc', *flags, '-c', str(c_path), '-o', str(work / 'full.o')])
            prelude_ms = median_ms(['cc', *flags, '-c', str(prelude_file), '-o', str(work / 'prelude.o')])
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            skipped.append((str(source.relative_to(CORPUS)), str(error)[:120]))
            continue
        row = dict(name=source.name, corpus=source.parent.name, c_bytes=len(text),
                   prelude_bytes=len(prelude), build_seconds=seconds, full_ms=full_ms,
                   prelude_ms=prelude_ms, path='general' if 'py_main' in text else 'typed')
        rows.append(row)
        print('%2d %-38s %-7s C=%7dB prelude=%5.1f%% full=%7.1fms prelude=%6.1fms'
              % (len(rows), str(source.relative_to(CORPUS)), row['path'], row['c_bytes'],
                 100.0 * len(prelude) / len(text), full_ms, prelude_ms), flush=True)

    total_full = sum(row['full_ms'] for row in rows)
    total_prelude = sum(row['prelude_ms'] for row in rows)
    floor = empty_ms * len(rows)
    shares = [(row['prelude_ms'] - empty_ms) / (row['full_ms'] - empty_ms) for row in rows]
    result = dict(flags=flags, empty_ms=empty_ms, rows=rows, skipped=skipped,
                  total_full_ms=total_full, total_prelude_ms=total_prelude,
                  prelude_share=(total_prelude - floor) / (total_full - floor),
                  mean_share=statistics.mean(shares), median_share=statistics.median(shares),
                  per_program_shares=sorted(shares))
    (work_root / 'result.json').write_text(json.dumps(result, indent=1))
    print(json.dumps({key: result[key] for key in (
        'flags', 'empty_ms', 'total_full_ms', 'total_prelude_ms', 'prelude_share',
        'mean_share', 'median_share', 'skipped')}, indent=1))
    print('rows and summary:', work_root)


if __name__ == '__main__':
    main()
