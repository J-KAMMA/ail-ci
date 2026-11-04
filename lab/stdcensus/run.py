#!/usr/bin/env python3
"""Reproducible census of CPython's pure-Python stdlib modules built by AIL.

    python3 lab/stdcensus/run.py -j 2 [--only NAME ...] [--timeout 120] [--deadline 1800]

Writes lab/stdcensus/results.jsonl, one JSON object per module (the order of
lab/stdcensus/modules.txt).  A local copy of CPython's module shadows AIL's model
of it; main.py is `import M; print("ok")`.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
STDLIB = Path(sysconfig.get_path('stdlib'))


INTEG_SHA = ''
BASELINE_SHA = ''


def _ident_ok(name):
    """True when `import <name>` is valid Python syntax."""
    return all(part.isidentifier() for part in name.split('.'))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _contributes(program_c, top):
    """True when generated C holds at least one symbol from the module.

    Real compiled definitions are named `<module>__name`; when AIL drops the
    module after accepting the import, program.c is only the runtime and holds
    no such symbol.
    """
    if not program_c.is_file():
        return True
    pat = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(top) + r'__[A-Za-z_]')
    return pat.search(program_c.read_text(errors='replace')) is not None


def build_baseline():
    """sha256 of the binary for a program with no import at all.

    A module whose build produces this exact binary contributed no code: AIL
    accepted the program but silently dropped the module.
    """
    tmp = Path(tempfile.mkdtemp(prefix='stdcensus-base-'))
    try:
        (tmp / 'main.py').write_text('print("ok")\n')
        env = dict(os.environ, AIL_NO_CACHE='1')
        cmd = [sys.executable, '-B', str(AIL), 'compile', 'main.py', '--syntax', 'python', '-o', 'main']
        p = subprocess.run(cmd, cwd=tmp, env=env, text=True, capture_output=True,
                           timeout=120, preexec_fn=_limits)
        if p.returncode != 0 or not (tmp / 'main').exists():
            raise SystemExit('baseline build failed: ' + p.stderr[-500:])
        return _sha256(tmp / 'main')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def discover_integ_sha():
    for ref in ('origin/integ', 'integ'):
        try:
            p = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--verify', ref], text=True,
                               capture_output=True, timeout=10)
            if p.returncode == 0:
                return p.stdout.strip()
        except Exception:
            pass
    # No integ ref here (an exported branch): the compiler files were last
    # changed by the commit whose code this census measures.
    try:
        p = subprocess.run(['git', '-C', str(ROOT), 'log', '-1', '--format=%H', '--', 'AIL_CURRENT'],
                           text=True, capture_output=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    try:
        return subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True,
                              capture_output=True, timeout=10).stdout.strip()
    except Exception:
        return ''


def integ_sha():
    return INTEG_SHA or discover_integ_sha()


def source_of(name):
    top = name.split('.')[0]
    d = STDLIB / top
    f = STDLIB / (top + '.py')
    if d.is_dir():
        return d, top, True
    if f.is_file():
        return f, top, False
    return None, top, False


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (1500000000, 1500000000))
    except Exception:
        pass


def _copy(src, top, is_pkg, dest):
    if is_pkg:
        shutil.copytree(src, dest / top, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        shutil.copy2(src, dest / (top + '.py'))


def _lines(text):
    return [x.strip() for x in text.splitlines() if x.strip()]


def _reasons(lines):
    keys = ('not in the subset:',)
    out, seen = [], set()
    for line in lines:
        if any(k in line for k in keys) and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def _first_reason(lines):
    useful = [x for x in lines if 'shadows the standard library module' not in x]
    return useful[0] if useful else ''


def census_one(name, timeout):
    t0 = time.monotonic()
    rec = {'name': name, 'result': 'not run', 'path': '', 'build_seconds': 0.0,
           'first_reason': '', 'reasons': [], 'python': sys.version.split()[0],
           'integ_sha': integ_sha()}
    src, top, is_pkg = source_of(name)
    if src is None:
        rec['result'] = 'absent'
        return rec
    rec['path'] = str(src)
    if not _ident_ok(name):
        rec['result'] = 'absent'
        rec['first_reason'] = ('name is not a Python identifier, so it cannot be written as an '
                               '`import` statement; CPython imports it through importlib')
        return rec
    tmp = Path(tempfile.mkdtemp(prefix='stdcensus-'))
    try:
        _copy(src, top, is_pkg, tmp)
        (tmp / 'main.py').write_text('import ' + name + '\nprint("ok")\n')
        env = dict(os.environ, AIL_NO_CACHE='1')
        cmd = [sys.executable, '-B', str(AIL), 'compile', 'main.py', '--syntax', 'python', '-o', 'main',
               '--debug-dir', 'dbg']
        try:
            p = subprocess.run(cmd, cwd=tmp, env=env, text=True, capture_output=True,
                               timeout=timeout, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            rec['result'] = 'timeout'
            rec['build_seconds'] = round(time.monotonic() - t0, 2)
            return rec
        rec['build_seconds'] = round(time.monotonic() - t0, 2)
        err = _lines(p.stderr)
        rec['first_reason'] = _first_reason(err)[:500]
        rec['reasons'] = [x[:1000] for x in _reasons(err)]
        if p.returncode != 0:
            rec['result'] = 'refused'
            rec['exit'] = p.returncode
            return rec
        built = 'built-general' if any('built on the general path' in x for x in err) else 'built-typed'
        rec['build_result'] = built
        binary = tmp / 'main'
        if not binary.exists():
            rec['result'] = 'wrong'
            rec['detail'] = 'compiler exited 0 but main was not created'
            return rec
        try:
            got = subprocess.run([str(binary)], cwd=tmp, text=True, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            rec['result'] = 'wrong'
            rec['detail'] = 'built program timed out'
            rec['build_result'] = built
            return rec
        want = subprocess.run([sys.executable, 'main.py'], cwd=tmp, text=True,
                              capture_output=True, timeout=60)
        rec['build_result'] = built
        if (got.returncode, got.stdout) != (want.returncode, want.stdout):
            rec['result'] = 'wrong'
            rec['detail'] = ('expected rc=%r stdout=%r, got rc=%r stdout=%r stderr=%r' %
                             (want.returncode, want.stdout, got.returncode, got.stdout,
                              got.stderr[-400:]))
        elif ((BASELINE_SHA and _sha256(binary) == BASELINE_SHA)
              or not _contributes(tmp / 'dbg' / 'program.c', top)):
            rec['result'] = 'built-empty'
            rec['first_reason'] = ('module source contributed no code: the generated program has '
                                   'no %s__ symbol (a bare print("ok") builds the same binary)' % top)
        else:
            rec['result'] = built
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('--only', nargs='+')
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--deadline', type=float, default=1800, help='whole-run seconds')
    ap.add_argument('--integ-sha', default='', help='base integ commit recorded in every record')
    ap.add_argument('-o', '--output', default=str(HERE / 'results.jsonl'))
    args = ap.parse_args()
    global INTEG_SHA, BASELINE_SHA
    INTEG_SHA = args.integ_sha or discover_integ_sha()
    BASELINE_SHA = build_baseline()
    names = [x.strip() for x in (HERE / 'modules.txt').read_text().splitlines() if x.strip()]
    if args.only:
        wanted = set(args.only)
        names = [x for x in names if x in wanted]
    start = time.monotonic()
    deadline = start + args.deadline
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        fut = {}
        for n in names:
            fut[ex.submit(census_one, n, args.timeout)] = n
        for f in concurrent.futures.as_completed(fut):
            n = fut[f]
            if time.monotonic() > deadline:
                results[n] = {'name': n, 'result': 'not run', 'path': '', 'build_seconds': 0.0,
                              'first_reason': '', 'reasons': [], 'python': sys.version.split()[0],
                              'integ_sha': integ_sha()}
                continue
            try:
                results[n] = f.result()
            except Exception as e:
                results[n] = {'name': n, 'result': 'refused', 'path': '', 'build_seconds': 0.0,
                              'first_reason': 'harness error: ' + repr(e), 'reasons': [],
                              'python': sys.version.split()[0], 'integ_sha': integ_sha()}
            print('%-42s %-14s %6.1fs' % (n, results[n]['result'], results[n]['build_seconds']),
                  flush=True)
    out = Path(args.output)
    with out.open('w') as fh:
        for n in names:
            fh.write(json.dumps(results.get(n, {'name': n, 'result': 'not run'}), sort_keys=True) + '\n')
    print('wrote', out, 'in %.1fs' % (time.monotonic() - start))


if __name__ == '__main__':
    main()
