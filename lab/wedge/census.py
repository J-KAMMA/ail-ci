#!/usr/bin/env python3
"""Hybrid + standalone census over lab/wedge/corpus (measurement only).

    python3 lab/wedge/census.py [-j 2] [-o lab/wedge/census.json]

For each corpus module `<kind>/<kind>.py` this builds
  * the CPython hybrid (`ail build --cpython <kind>.py -o DIR`), and
  * the standalone binary from the driver (`ail compile run.py --syntax python -o exe`),
records which top-level functions went native and, for every function that stayed on
CPython, the reason the hybrid gives, and compares the driver's stdout, exit status and last
stderr line with `python3 run.py`.
"""
import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AIL = ROOT / 'AIL_CURRENT' / 'ail_chatgpt.py'
CORPUS = HERE / 'corpus'
TIMEOUT = 300


def _run(cmd, cwd, timeout=TIMEOUT):
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or b'', e.stderr or b''


def _last(data):
    text = data.decode('utf-8', 'replace').rstrip('\n')
    lines = text.splitlines()
    return lines[-1] if lines else ''


def _detail(want, got):
    a = want.decode('utf-8', 'replace').splitlines()
    b = got.decode('utf-8', 'replace').splitlines()
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<missing>'
        y = b[i] if i < len(b) else '<missing>'
        if x != y:
            return 'stdout line %d: CPython %r / got %r' % (i + 1, x[:160], y[:160])
    return None


def module_dirs():
    return sorted(p for p in CORPUS.iterdir() if (p / 'run.py').is_file())


def census_one(kind_dir):
    kind = kind_dir.name
    rec = {'module': kind, 'hybrid': {}, 'standalone': {}, 'match': {}}
    work = Path(tempfile.mkdtemp(prefix='wedge-%s-' % kind))
    try:
        for f in kind_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, work / f.name)
        rec['functions'] = sorted(
            l.split('(')[0][4:].strip()
            for l in (work / (kind + '.py')).read_text().splitlines()
            if l.startswith('def '))
        # strict build: does the whole module type?
        rc, out, err = _run([sys.executable, '-B', str(AIL), 'compile', kind + '.py',
                             '--syntax', 'python', '--strict', '-o', str(work / 'strict.out')],
                            work)
        rec['strict_rc'] = rc
        blockers = []
        if rc != 0:
            try:
                doc = json.loads(out.decode('utf-8', 'replace'))
                blockers = [{'function': b.get('function'), 'line': b.get('line'),
                             'construct': b.get('construct'), 'why': b.get('why'),
                             'message': (b.get('message') or '')[:200]}
                            for b in doc.get('blockers') or []]
            except Exception:
                blockers = [{'message': _last(err)[:200]}]
        rec['strict_blockers'] = blockers
        # CPython
        rc0, out0, err0 = _run([sys.executable, '-B', 'run.py'], work)
        rec['cpython'] = {'rc': rc0, 'stdout': out0.decode('utf-8', 'replace'),
                          'last_err': _last(err0)}
        # hybrid
        hdir = work / 'hybrid'
        t0 = time.monotonic()
        rc, out, err = _run([sys.executable, '-B', str(AIL), 'build', '--cpython',
                             kind + '.py', '-o', str(hdir)], work)
        rec['hybrid']['build_s'] = round(time.monotonic() - t0, 2)
        rec['hybrid']['build_rc'] = rc
        if rc == 0:
            try:
                report = json.loads((hdir / 'build.json').read_text())
            except Exception:
                report = {}
            rec['hybrid']['accelerated'] = sorted(report.get('accelerated') or [])
            rec['hybrid']['rejected'] = report.get('rejected') or {}
            rec['hybrid']['note'] = report.get('note') or ''
            shutil.copy2(work / 'run.py', hdir / 'run.py')
            rc1, out1, err1 = _run([sys.executable, '-B', 'run.py'], hdir)
            rec['hybrid']['rc'] = rc1
            same = (rc1 == rc0 and out1 == out0 and _last(err1) == _last(err0))
            rec['match']['hybrid'] = same
            rec['hybrid']['detail'] = '' if same else (
                _detail(out0, out1) or 'rc %s vs %s / last err %r vs %r'
                % (rc0, rc1, _last(err0)[:120], _last(err1)[:120]))
        else:
            rec['hybrid']['accelerated'] = []
            rec['hybrid']['rejected'] = {}
            rec['hybrid']['detail'] = _last(err)[:300]
            rec['match']['hybrid'] = False
        # standalone
        t0 = time.monotonic()
        rc, out, err = _run([sys.executable, '-B', str(AIL), 'compile', 'run.py',
                             '--syntax', 'python', '-o', str(work / 'exe')], work)
        rec['standalone']['build_s'] = round(time.monotonic() - t0, 2)
        rec['standalone']['build_rc'] = rc
        note = [l.strip() for l in err.decode('utf-8', 'replace').splitlines()
                if 'general path' in l or 'typed path' in l]
        rec['standalone']['path_note'] = note[0][:300] if note else ''
        rec['standalone']['general'] = bool(note) and 'general path' in note[0]
        if rc == 0:
            rc2, out2, err2 = _run([str(work / 'exe')], work)
            rec['standalone']['rc'] = rc2
            same = (rc2 == rc0 and out2 == out0 and _last(err2) == _last(err0))
            rec['standalone']['detail'] = '' if same else (
                _detail(out0, out2) or 'rc %s vs %s / last err %r vs %r'
                % (rc0, rc2, _last(err0)[:120], _last(err2)[:120]))
            rec['match']['standalone'] = same
            if rc2 != 0 and _last(err2):
                # A loud int64 stop.  `--exact-int` is the documented flag for it; retry so the
                # report can say whether the flag alone makes the program build and match.
                rec['standalone']['stop'] = _last(err2)[:200]
                rc3, _out, _err = _run([sys.executable, '-B', str(AIL), 'compile', 'run.py',
                                        '--syntax', 'python', '--exact-int',
                                        '-o', str(work / 'exe_exact')], work)
                if rc3 == 0:
                    rc4, out4, err4 = _run([str(work / 'exe_exact')], work)
                    rec['standalone']['exact_int_rc'] = rc4
                    rec['standalone']['exact_int_match'] = bool(
                        rc4 == rc0 and out4 == out0 and _last(err4) == _last(err0))
                else:
                    rec['standalone']['exact_int_build_rc'] = rc3
                    rec['standalone']['exact_int_error'] = _last(_err)[:200]
        else:
            rec['standalone']['detail'] = _last(err)[:300]
            rec['match']['standalone'] = False
        return rec
    except Exception as error:
        rec['error'] = '%s: %s' % (type(error).__name__, str(error)[:300])
        return rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-j', '--jobs', type=int, default=2)
    ap.add_argument('-o', '--out', default=str(HERE / 'census.json'))
    ap.add_argument('--only')
    args = ap.parse_args()
    dirs = module_dirs()
    if args.only:
        keep = set(args.only.split(','))
        dirs = [d for d in dirs if d.name in keep]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {ex.submit(census_one, d): d for d in dirs}
        for f in concurrent.futures.as_completed(futs):
            rec = f.result()
            rows.append(rec)
            h = rec.get('hybrid', {})
            s = rec.get('standalone', {})
            print('%-14s functions=%-2d native=%-2d hybrid=%-5s standalone=%-5s %s' % (
                rec['module'], len(rec.get('functions') or []), len(h.get('accelerated') or []),
                rec.get('match', {}).get('hybrid'), rec.get('match', {}).get('standalone'),
                (h.get('detail') or s.get('detail') or '')[:90]), flush=True)
    rows.sort(key=lambda r: r['module'])
    Path(args.out).write_text(json.dumps(rows, indent=1) + '\n')
    total = sum(len(r.get('functions') or []) for r in rows)
    native = sum(len((r.get('hybrid') or {}).get('accelerated') or []) for r in rows)
    print('modules %d  functions %d  native %d (%.1f%%)  wrote %s'
          % (len(rows), total, native, 100.0 * native / max(1, total), args.out))


if __name__ == '__main__':
    main()
