#!/usr/bin/env python3
"""Typed-reach census of the repository's plain-Python programs.

    python3 lab/pyproof/report.py [-j 2] [--programs FILE] [--out DIR] [--only PATH ...]

For every program in programs.txt:

* build with ``--strict`` (typed, or the refusal text);
* build with the default command (typed, general with the ``note:`` reason, or
  refused);
* run the default binary and ``python3`` on the same input, compare stdout and
  the exit status (``wrong`` when the build succeeded but the output differs);
* time both (median of three, CPython run capped at 2 s).

Writes ``results.jsonl`` and ``RESULTS.md`` under ``--out`` (default: this
directory).  At most ``--jobs`` builds run at once; each build/run is capped at
1.5 GB of address space and builds expire after 120 s.
"""
import argparse
import concurrent.futures
import json
import math
import os
import random
import re
import resource
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
BUILD_TIMEOUT = 120
CPYTHON_TIMEOUT = 2.0
AIL_RUN_TIMEOUT = 20.0
BUCKET_REPRO = HERE / 'repro'


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (1500000000, 1500000000))
    except Exception:
        pass


def integ_sha():
    for ref in ('origin/integ', 'integ'):
        try:
            p = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--verify', ref], text=True,
                               capture_output=True, timeout=10)
            if p.returncode == 0:
                return p.stdout.strip()
        except Exception:
            pass
    try:
        return subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True,
                              capture_output=True, timeout=10).stdout.strip()
    except Exception:
        return ''


SHA = ''


def load_programs(path):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '\t' in line:
            p, spec = line.split('\t', 1)
        else:
            p, _, spec = line.partition(' ')
        out.append((p.strip(), (spec or 'none').strip()))
    return out


def source_path(p):
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def first_reason(text):
    lines = [x.strip() for x in (text or '').splitlines() if x.strip()]
    lines = [x for x in lines if not x.startswith('{')]
    for line in lines:
        if 'not in the subset:' in line:
            return line
    for line in lines:
        if 'why not typed:' in line:
            return line
    for line in lines:
        if not line.startswith('strict:') and 'write instead:' not in line:
            return line
    return lines[0] if lines else ''


def reasons(text):
    out, seen = [], set()
    for line in (text or '').splitlines():
        line = line.strip()
        if ('not in the subset:' in line or 'why not typed:' in line) and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def prepare_input(spec, work, name):
    """Return (args, stdin_path) for the program."""
    if spec in ('none', ''):
        return [], None
    if spec.startswith('stdin:'):
        return [], source_path(spec[6:])
    if spec.startswith('argv:'):
        parts = shlex.split(spec[5:])
        return [a.replace('{work}', str(work)) for a in parts], None
    if spec.startswith('gen:'):
        task_dir = source_path(spec[4:])
        gen_path = task_dir / 'gen.py'
        modname = 'pyproof_gen_' + re.sub(r'\W', '_', task_dir.name)
        import importlib.util
        spec_obj = importlib.util.spec_from_file_location(modname, gen_path)
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
        public, _hidden, _perf = module.cases(random.Random(task_dir.name + '-20261012'))
        _case_name, data, args = public[0]
        if isinstance(data, str):
            data = data.encode()
        input_path = work / 'input.bin'
        input_path.write_bytes(data)
        args = [a.replace('{input}', str(input_path)) for a in args]
        stdin_path = input_path if getattr(module, 'STDIN', False) else None
        return args, stdin_path
    raise SystemExit('unknown input spec for %s: %r' % (name, spec))


def _run(cmd, cwd, stdin_path, timeout, env=None):
    fh = open(stdin_path, 'rb') if stdin_path else subprocess.DEVNULL
    started = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, stdin=fh, capture_output=True, text=False,
                           timeout=timeout, env=env, preexec_fn=_limits)
        return {'rc': p.returncode, 'out': p.stdout, 'err': p.stderr,
                'seconds': time.monotonic() - started, 'timeout': False}
    except subprocess.TimeoutExpired as e:
        return {'rc': None, 'out': (e.stdout or b''), 'err': (e.stderr or b''),
                'seconds': time.monotonic() - started, 'timeout': True}
    finally:
        if stdin_path:
            fh.close()


def _timed(cmd, cwd, stdin_path, timeout, env, runs=3):
    times, first = [], None
    for _ in range(runs):
        got = _run(cmd, cwd, stdin_path, timeout, env)
        if first is None:
            first = got
        if got['timeout']:
            break
        times.append(got['seconds'])
    first = first or {'rc': None, 'out': '', 'err': '', 'seconds': None, 'timeout': True}
    first['median'] = statistics.median(times) if times else None
    return first


def _build(src_name, out, strict, work):
    cmd = [sys.executable, '-B', str(AIL), 'compile', src_name, '--syntax', 'python']
    if strict:
        cmd.append('--strict')
    cmd.extend(['-o', out])
    env = dict(os.environ, AIL_NO_CACHE='1',
               PYTHONPATH=str(ROOT / 'AIL_CURRENT') + os.pathsep + os.environ.get('PYTHONPATH', ''))
    try:
        p = subprocess.run(cmd, cwd=str(work), text=True, capture_output=True,
                           timeout=BUILD_TIMEOUT, env=env, preexec_fn=_limits)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'build timed out after %d s' % BUILD_TIMEOUT


def census_one(program, spec):
    src = source_path(program)
    rec = {'name': program, 'path': str(src), 'input': spec, 'result': 'not run',
           'python': sys.version.split()[0], 'integ_sha': SHA, 'build_seconds': 0.0}
    work = Path(tempfile.mkdtemp(prefix='pyproof-'))
    try:
        for f in src.parent.glob('*.py'):
            if f.is_file():
                shutil.copy2(f, work / f.name)
        # a small deterministic file for the crate bench programs
        (work / 'input.bin').write_bytes(b'the quick brown fox jumps over the lazy dog\n' * 50)
        args, stdin_path = prepare_input(spec, work, program)
        start = time.monotonic()
        rc, _out, err = _build(src.name, 'strict.out', True, work)
        strict_typed = rc == 0
        rec['strict_path'] = 'typed' if strict_typed else 'refused'
        rec['strict_reason'] = '' if strict_typed else first_reason(err)[:600]
        rc, _out, err = _build(src.name, 'main.out', False, work)
        rec['build_seconds'] = round(time.monotonic() - start, 2)
        if rc != 0:
            rec['result'] = 'refused'
            rec['first_reason'] = first_reason(err)[:600]
            rec['reasons'] = [x[:1000] for x in reasons(err)]
            return rec
        general = 'built on the general path' in (err or '')
        rec['default_path'] = 'general' if general else 'typed'
        if general:
            note = ''
            for line in (err or '').splitlines():
                if 'built on the general path' in line:
                    note = line.strip()
                    break
            rec['note'] = note[:600]
            rec['first_reason'] = note[:600]
        binary = work / 'main.out'
        if not binary.exists():
            rec['result'] = 'wrong'
            rec['detail'] = 'compiler exited 0 but main.out was not created'
            return rec
        env = dict(os.environ, PYTHONPATH=str(work) + os.pathsep + str(ROOT / 'AIL_CURRENT') +
                   os.pathsep + os.environ.get('PYTHONPATH', ''))
        expected = _timed([sys.executable, '-B', src.name, *args], work, stdin_path,
                          CPYTHON_TIMEOUT, env, 3)
        actual = _timed([str(binary), *args], work, stdin_path, AIL_RUN_TIMEOUT, env, 3)
        rec['exit_cpython'] = expected['rc']
        rec['exit_ail'] = actual['rc']
        rec['stdout_equal'] = expected['out'] == actual['out']
        rec['cpython_seconds'] = round(expected['median'], 4) if expected['median'] else None
        rec['ail_seconds'] = round(actual['median'], 4) if actual['median'] else None
        if rec['cpython_seconds'] and rec['ail_seconds']:
            rec['speedup'] = round(rec['cpython_seconds'] / rec['ail_seconds'], 3)
        if actual['rc'] != 0 or expected['out'] != actual['out']:
            rec['result'] = 'wrong'
            rec['detail'] = ('expected rc=%r stdout=%r, got rc=%r stdout=%r stderr=%r' %
                             (expected['rc'], expected['out'][:300].decode('utf-8', 'replace'),
                              actual['rc'], actual['out'][:300].decode('utf-8', 'replace'),
                              actual['err'][-400:].decode('utf-8', 'replace')))
        else:
            rec['result'] = rec['default_path']
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def strip_location(line):
    s = line.strip()
    if s.startswith('note: '):
        s = s[6:]
    s = re.sub(r'^[^\s:]+\.py:\d+(?::\d+)?: ', '', s)
    s = re.sub(r'^[^\s:]+:\d+(?::\d+)?: ', '', s)
    if s.startswith('not in the subset: '):
        s = s[len('not in the subset: '):]
    if s.startswith('why not typed: '):
        s = s[len('why not typed: '):]
    return s.strip()


def normalise(line):
    s = strip_location(line)
    s = re.sub(r'^built on the general path \(about \d+x slower\) because ', '', s)
    s = re.sub(r'; run with --strict to see why$', '', s)
    s = re.sub(r'\.?\s*write instead:.*$', '', s)
    s = re.sub(r' \(the general path could not build this program either\)', '', s)
    s = re.sub(r'; general path:.*$', '', s)
    s = s.strip()
    if re.match(r'^build timed out after \d+ s$', s):
        return ''
    rules = [
        (r'^import of \'([^\']+)\' is not available:.*$', "import of 'X' is not available"),
        (r"^'[^']+' is a list parameter, which is read-only;.*$", 'a list parameter is read-only'),
        (r'^the constant None;.*$', 'the constant None'),
        (r'^yield: this language has no generators\.?.*$', 'this language has no generators'),
        (r'^a generator expression saved as a value.*$',
         'a generator expression saved as a value'),
        (r'^`[^`]*` uses `[^`]*` as a dict of containers.*$',
         'a dict of containers (lists, sets or dicts as values)'),
        (r'^line \d+: `[^`]*` makes a second reference to the same container.*$',
         'a second reference to the same container'),
        (r"^'[^']+' is a module-level constant; storing into it.*$",
         'a module-level constant is stored into'),
        (r'^field `[^`]+` requires a class instance.*$', 'a field requires a class instance'),
        (r'^main: .* is read by a nested lambda.*$',
         'a name is read by a nested lambda before assignment'),
        (r'^fields returns a tuple on one path and a single value on another.*$',
         'a function returns a tuple on one path and a single value on another'),
        (r'^Markdown\.__init__ must take plain positional arguments.*$',
         'a method must take plain positional arguments'),
        (r'^a int holds integers;.*$', 'an int field holds integers, a float would truncate'),
        (r'^int64 (?:literal )?out of range: .*$',
         'an integer literal or constant expression overflows int64'),
        (r'^int64 constant expression out of range.*$',
         'an integer literal or constant expression overflows int64'),
        (r'^a constant integer expression overflows int64:.*$',
         'an integer literal or constant expression overflows int64'),
        (r"^'[^']+' is a module-level list of non-numbers;.*$",
         'a module-level list of non-numbers'),
        (r'^field `[^`]+` is a list or dict that gets bools and numbers.*$',
         'a field list or dict gets bools and numbers'),
        (r"^import of '[^']+' with a use that is not built:.*$",
         "import of 'X' with a use that is not built"),
        (r'^library\(\) returns a path without saying so.*$',
         'a function returns a path without saying so'),
        (r'^(\w[\w.]*) is not built\. Built:.*$', 'X is not built'),
        (r'^(\w[\w.]*) used here is not built\. Built:.*$', 'X used here is not built'),
        (r'^using function \S+ as a first-class value.*$',
         'using function X as a first-class value'),
        (r'^a dict view kept in a name.*$',
         'a dict view kept in a name, field, item or container'),
        (r'^a class-level constant built through .*$',
         'a class-level constant built through a list item, attribute or dict value'),
        (r'^import of a local module or package below the top level.*$',
         'import of a local module or package below the top level'),
        (r"^import of the CPython C module '[^']+' guarded by .*$",
         "import of 'X' guarded by except ImportError"),
        (r"^module '([^']+)' has no top-level name '([^']+)' \(it defines:.*$",
         "module 'X' has no top-level name 'Y'"),
        (r"^'[^']+' is imported and also assigned or defined again.*$",
         "'X' is imported and also assigned or defined again"),
        (r'^class \S+ bases on .*$', 'class X bases on a type defined after it or unknown'),
        (r'^a caught exception type .*$',
         'a caught exception type (only builtin or user Exception subclasses are supported)'),
        (r'^isinstance\(\) against an unknown type .*$',
         'isinstance() against an unknown type'),
        (r"^name '[^']+' is not defined$", "name 'X' is not defined"),
        (r'^(\w[\w.]*) \(not yet published in NAMES_library\.json\)$',
         'X (not yet published in NAMES_library.json)'),
        (r'^str\.encode\(\) with the error handler \'[^\']+\'.*$',
         'str.encode() with an unsupported error handler on the general path'),
        (r'^str\.encode\(\) with the encoding \'[^\']+\'.*$',
         'str.encode() with an unsupported encoding on the general path'),
        (r'^open\(\) with a mode that is not a string literal.*$',
         'open() with a mode that is not a string literal'),
        (r'^a generator function in a program with threads.*$',
         'a generator function in a program with threads'),
        (r'^`with` around a `yield`.*$', '`with` around a `yield`'),
        (r'^a non-BMP string literal.*$', 'a non-BMP string literal in the 16-bit v2 runtime'),
        (r'^int64 constant expression out of range: \d+$',
         'int64 constant expression out of range'),
        (r'^\.__dataclass_fields__:.*$',
         '.__dataclass_fields__: the dataclass field table is not modelled'),
        (r'^a non-name base class.*$', 'a non-name base class'),
        (r'^function-level .*$', 'function-level import or definition is not built'),
        (r'^one `import` statement mixes .*$',
         'one import statement mixes local modules and others'),
        (r'^`__exit__` uses \'traceback\'.*$',
         "__exit__ uses 'traceback' other than in is None"),
        (r'^the decorator on def .*$', 'the decorator on a def'),
    ]
    for pat, rep in rules:
        if re.match(pat, s):
            return rep
    s = re.sub(r'`[^`]*`', '`X`', s)
    s = re.sub(r"'[^']*'", "'X'", s)
    s = re.sub(r'"[^"]*"', '"X"', s)
    s = re.sub(r'\b\d+\b', 'N', s)
    s = re.sub(r'\b\d+\.\d+\b', 'N', s)
    return s


def rec_reasons(rec):
    out = list(rec.get('reasons') or [])
    first = rec.get('first_reason') or ''
    if first and first not in out:
        out.insert(0, first)
    return out


def bucket_counts(recs):
    buckets = {}
    for r in recs:
        if r.get('result') not in ('refused', 'general'):
            continue
        bs = []
        for line in rec_reasons(r):
            b = normalise(line)
            if b and b not in bs:
                bs.append(b)
        for b in bs:
            buckets.setdefault(b, {'alone': 0, 'listed': 0, 'names': []})
            buckets[b]['listed'] += 1
            buckets[b]['names'].append(r['name'])
        if len(bs) == 1:
            buckets[bs[0]]['alone'] += 1
    return buckets


def slug(text):
    s = text.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:70].strip('-')


def cut(text, n):
    text = str(text).replace('\n', ' ')
    return text if len(text) <= n else text[:n - 3] + '...'


def geomean(values):
    values = [v for v in values if v and v > 0]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def render(recs, out_dir):
    counts = {}
    for r in recs:
        counts[r['result']] = counts.get(r['result'], 0) + 1
    wrong = [r for r in recs if r['result'] == 'wrong']
    built = [r for r in recs if r['result'] in ('typed', 'general')]
    speeds = [r.get('speedup') for r in built if r.get('speedup')]
    g = geomean(speeds)
    buckets = bucket_counts(recs)
    rows = sorted(buckets.items(), key=lambda kv: (-kv[1]['alone'], -kv[1]['listed'], kv[0]))

    lines = []
    lines.append('# pyproof: typed reach of the repository plain-Python programs')
    lines.append('')
    lines.append('Generated by `lab/pyproof/report.py` from `lab/pyproof/programs.txt` and '
                 '`lab/pyproof/results.jsonl`.')
    lines.append('')
    lines.append('- Base: integ `%s`' % (recs[0].get('integ_sha') if recs else 'unknown'))
    lines.append('- Oracle: CPython %s (`python3`), stdout and exit status' %
                 (recs[0].get('python') if recs else 'unknown'))
    lines.append('- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC --syntax python '
                 '[-o OUT] [--strict]`, `AIL_NO_CACHE=1`, 120 s, 1.5 GB, 2 at a time')
    lines.append('- Programs: `lab/pyproof/programs.txt` (%d, fixed order)' % len(recs))
    lines.append('')
    headline = 'typed %d / %d, general %d, refused %d, wrong %d' % (
        counts.get('typed', 0), len(recs), counts.get('general', 0),
        counts.get('refused', 0), counts.get('wrong', 0))
    lines.append('**%s**; geomean speed-up over CPython of the programs that build: %s.' %
                 (headline, 'n/a' if g is None else '%.2fx' % g))
    lines.append('')
    if wrong:
        lines.append('## WRONG (silent or loud differences)')
        lines.append('')
        for r in wrong:
            lines.append('- `%s`: %s' % (r['name'], cut(r.get('detail', ''), 300)))
        lines.append('')
    lines.append('## Counts')
    lines.append('')
    for k in ('typed', 'general', 'refused', 'wrong', 'not run'):
        if counts.get(k):
            lines.append('- **%s**: %d' % (k, counts[k]))
    lines.append('')
    lines.append('A program is **typed** when the default build prints no fallback note, '
                 '**general** when it prints `note: ... built on the general path ...`, '
                 '**refused** when the build exits non-zero, and **wrong** when it builds but '
                 'the run does not match CPython.')
    lines.append('')
    lines.append('## Programs')
    lines.append('')
    lines.append('| program | input | result | build s | CPython s | AIL s | speed-up | first reason |')
    lines.append('|---|---|---|---:|---:|---:|---:|---|')
    for r in recs:
        lines.append('| `%s` | %s | %s | %.1f | %s | %s | %s | %s |' % (
            r['name'], cut(r.get('input', ''), 40), r['result'], r.get('build_seconds', 0.0),
            'n/a' if r.get('cpython_seconds') is None else '%.3f' % r['cpython_seconds'],
            'n/a' if r.get('ail_seconds') is None else '%.3f' % r['ail_seconds'],
            'n/a' if not r.get('speedup') else '%.2fx' % r['speedup'],
            cut((r.get('first_reason') or '').replace('|', '\\|'), 160)))
    lines.append('')
    lines.append('## Blocker buckets')
    lines.append('')
    lines.append('A bucket is a refusal text with names and numbers replaced by placeholders. '
                 '**alone** counts programs whose only reason is this bucket; **listed** counts '
                 'programs that mention it at all. Sorted by alone, then listed.')
    lines.append('')
    lines.append('| alone | listed | bucket | reproducer |')
    lines.append('|---:|---:|---|---|')
    for b, info in rows:
        p = BUCKET_REPRO / (slug(b) + '.py')
        rel = '`lab/pyproof/repro/%s.py`' % slug(b) if p.exists() else ''
        lines.append('| %d | %d | %s | %s |' %
                     (info['alone'], info['listed'], b.replace('|', '\\|'), rel))
    lines.append('')
    lines.append('## Reproducers')
    lines.append('')
    top = []
    for b, info in rows:
        p = BUCKET_REPRO / (slug(b) + '.py')
        if p.exists() and len(top) < 10:
            top.append((b, p))
    if top:
        for b, p in top:
            lines.append('### `%s`' % p.name)
            lines.append('')
            lines.append('Bucket: %s' % b)
            lines.append('')
            lines.append('```python')
            lines.append(p.read_text().rstrip('\n'))
            lines.append('```')
            lines.append('')
    else:
        lines.append('No reproducer files found.')
        lines.append('')
    (Path(out_dir) / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    return counts, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('--programs', default=str(HERE / 'programs.txt'))
    ap.add_argument('--out', default=str(HERE))
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--render-only', action='store_true',
                    help='render RESULTS.md from an existing results.jsonl')
    args = ap.parse_args()
    global SHA
    SHA = integ_sha()
    out = Path(args.out)
    if args.render_only:
        recs = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()
                if line.strip()]
        render(recs, out)
        return
    programs = load_programs(args.programs)
    if args.only:
        wanted = set(args.only)
        programs = [(p, s) for p, s in programs if p in wanted]
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futures = {ex.submit(census_one, p, s): p for p, s in programs}
        for f in concurrent.futures.as_completed(futures):
            p = futures[f]
            try:
                r = f.result()
            except Exception as e:
                r = {'name': p, 'result': 'not run', 'first_reason': 'harness error: %r' % e,
                     'path': str(source_path(p)), 'python': sys.version.split()[0],
                     'integ_sha': SHA, 'build_seconds': 0.0}
            results[p] = r
            print('%-62s %-10s %6.1fs' % (p, r['result'], r.get('build_seconds', 0.0)), flush=True)
    recs = [results[p] for p, _ in programs]
    with (out / 'results.jsonl').open('w') as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    counts, rows = render(recs, out)
    print('wrote %s and %s in %.1fs: %s' % (out / 'results.jsonl', out / 'RESULTS.md',
          time.monotonic() - start,
          ', '.join('%s %d' % (k, counts[k]) for k in sorted(counts))))
    for b, info in rows[:15]:
        print('%3d %3d %s' % (info['alone'], info['listed'], b))


if __name__ == '__main__':
    main()
