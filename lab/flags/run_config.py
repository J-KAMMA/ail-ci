#!/usr/bin/env python3
"""Build and measure every workload with one compiler/flags config.

    python3 lab/flags/run_config.py --config gcc-O3 --out result.json [--smoke] [--only a,b]

Per program: build with gcc -O2 (reference) and with the config, run both, require identical stdout,
exit code and output file (and the bench oracle where one exists), then record instructions (callgrind
Ir; perf instructions when valgrind is missing), peak RSS (KiB) and stripped size (bytes).
Exit 1 on any mismatch or build failure."""
import argparse, hashlib, json, os, re, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import workloads


def cli(env, work, *args):
    r = subprocess.run([sys.executable, '-B', str(REPO / 'AIL_CURRENT/ail_chatgpt.py'), *map(str, args)],
                       cwd=work, env=env, capture_output=True, timeout=900)
    if r.returncode:
        raise RuntimeError('ail %s failed: %s' % (args[0], r.stderr.decode(errors='replace')[-1500:]))


def make_env(cfg, base, **extra):
    env = dict(os.environ)
    env.update(PIPE_CC=str(HERE / 'ccwrap.py'), PIPE_CACHE=str(base / 'cache'), FLAGS_CC=cfg['cc'],
               FLAGS_OPT=cfg.get('opt', '-O2'), FLAGS_EXTRA=cfg.get('extra', ''), FLAGS_PGO='')
    env.update(extra)
    return env


def build(spec, env, work, label):
    d = work / label
    d.mkdir()
    if spec['prepare']:
        data = work / 'data'  # where the options expect module objects
        for old in data.glob("*.o*"):
            old.unlink()
        spec['prepare'](data, lambda *a: cli(env, d, *a))
    out = d / 'prog'
    cli(env, d, 'compile', spec['source'], *spec['options'], '-o', out)
    return out


def argv_for(binary, case, work):
    return [str(binary)] + [a.replace('{out}', str(work / 'run.out')) for a in case['args']]


def run(binary, case, work):
    out = work / 'run.out'
    out.unlink(missing_ok=True)
    p = subprocess.run(argv_for(binary, case, work), capture_output=True, timeout=600)
    h = hashlib.sha256(p.stdout)
    h.update(b'|%d|' % p.returncode)
    if out.is_file():
        h.update(out.read_bytes())
    ok = p.returncode == 0
    if ok and case.get('expected_stdout') is not None and p.stdout != case['expected_stdout']:
        ok = False
    if ok and case.get('expected_file') is not None and (not out.is_file() or out.read_bytes() != case['expected_file']):
        ok = False
    out.unlink(missing_ok=True)
    return h.hexdigest(), ok


def instructions(binary, case, work):
    argv = argv_for(binary, case, work)
    if shutil.which('valgrind'):
        cg = work / 'cg.out'
        p = subprocess.run(['valgrind', '--tool=callgrind', '--callgrind-out-file=' + str(cg), *argv],
                           capture_output=True, timeout=3000)
        m = re.search(rb'Collected\s*:\s*(\d+)', p.stderr)
        cg.unlink(missing_ok=True)
        return int(m.group(1)) if m else None
    icount = work.parent / 'icount'  # local fallback: perf_event_open counter from tools/icount.c
    if not icount.is_file():
        subprocess.run(['cc', '-O2', '-w', '-include', 'signal.h', '-include', 'stdlib.h', '-o', str(icount),
                        str(REPO / 'tools/icount.c')], check=True)
    p = subprocess.run([str(icount), *argv], capture_output=True, timeout=600)
    return int(p.stdout.split()[-1]) if p.returncode == 0 and p.stdout.strip() else None


def rss_kib(binary, case, work):
    vals = []
    for _ in range(3):
        t = work / 'time.txt'
        subprocess.run(['/usr/bin/time', '-f', '%M', '-o', str(t), '--', *argv_for(binary, case, work)],
                       capture_output=True, timeout=600)
        (work / 'run.out').unlink(missing_ok=True)
        words = t.read_text(errors='replace').split()
        if words and words[-1].isdigit():
            vals.append(int(words[-1]))
    return int(statistics.median(vals)) if vals else None


def stripped_size(binary, work):
    copy = work / 'stripped'
    shutil.copyfile(binary, copy)
    subprocess.run(['strip', str(copy)], check=True)
    n = copy.stat().st_size
    copy.unlink()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    configs = json.loads((HERE / 'configs.json').read_text())
    cfg, ref_cfg = configs[a.config], configs['gcc-O2']
    names = a.only.split(',') if a.only else workloads.names()
    base = Path(tempfile.mkdtemp(prefix='flags-'))
    results, bad = {}, 0
    for name in names:
        row = {}
        work = base / name
        t0 = time.time()
        try:
            spec = workloads.build_spec(name, work / 'data', a.smoke)
            case = spec['case']
            ref = build(spec, make_env(ref_cfg, work), work, 'ref')
            ref_hash, ref_ok = run(ref, case, work)
            if not ref_ok:
                raise RuntimeError('gcc -O2 reference fails its oracle or exits nonzero')
            if cfg.get('pgo'):
                fix = work / 'pgo'
                gen = build(spec, make_env(cfg, work, FLAGS_PGO='gen', FLAGS_FIXDIR=str(fix)), work, 'gen')
                run(gen, case, work)  # training run on the same example input
                cand = build(spec, make_env(cfg, work, FLAGS_PGO='use', FLAGS_FIXDIR=str(fix)), work, 'cand')
            elif a.config == 'gcc-O2':
                cand = ref
            else:
                cand = build(spec, make_env(cfg, work), work, 'cand')
            cand_hash, cand_ok = run(cand, case, work)
            if cand_hash != ref_hash or not cand_ok:
                row['status'] = 'MISMATCH'
                bad += 1
            else:
                row.update(status='ok', ir=instructions(cand, case, work), rss_kib=rss_kib(cand, case, work),
                           size=stripped_size(cand, work))
        except Exception as e:  # a build or run failure counts against the config
            row.update(status='ERROR', error=str(e)[-600:])
            bad += 1
        row['seconds'] = round(time.time() - t0, 1)
        results[name] = row
        print(a.config, name, row, flush=True)
        shutil.rmtree(work, ignore_errors=True)
    Path(a.out).write_text(json.dumps({'config': a.config, 'results': results}, indent=1))
    shutil.rmtree(base, ignore_errors=True)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
