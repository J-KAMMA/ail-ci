"""Compare AIL (a base commit and the working tree) with C and Rust on the public apps.

    python3 bench/compare.py                      # all apps, base = HEAD
    python3 bench/compare.py --base HEAD~1 --app binary_cursor_records

Every arm must pass the app's boundary controls, and every timed run's output is checked
byte-for-byte against the app's independent Python oracle. Arms run interleaved run by run
(one AIL-base/AIL-new/C/Rust round per step, rotating the order), pinned to one CPU. Each window
of ROUNDS rounds yields a per-window time ratio; the table shows the median and the rank-2..8
range of the nine windows. A range that crosses 1.0 is a tie. Linux only.

Beside time the table has peak RSS, binary size and build disk: KiB one release build adds under a fresh build
dir and fresh cache (AIL_CACHE, TMPDIR; see build_disk_kib), measured in a separate pass after the timing. A last line
gives the toolchain install size per language (`du -sk`), once.

App modules (bench/apps/<name>.py) define AIL_SOURCE, AIL_OPTIONS, optional prepare_ail(work, cli),
C_SOURCE, RUST_SOURCE, STRATEGY, REFERENCE_SCOPE, controls(work) and generate(work, smoke).
"""
import argparse, importlib.util, itertools, json, os, re, shutil, statistics, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APPS = sorted(p.stem for p in (REPO / 'bench/apps').glob('*.py'))
C_FLAGS = ['-std=gnu11', '-O3', '-march=native', '-flto']
RUST_FLAGS = ['-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'codegen-units=1', '-C', 'lto=fat', '--edition=2021']
WINDOWS = 9


def load_app(name):
    spec = importlib.util.spec_from_file_location('app_' + name, REPO / 'bench/apps' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_ail(app, ail_root, work, label, env=None):
    work = work / ('build-' + label)
    work.mkdir()
    def cli(*args):
        result = subprocess.run([sys.executable, '-B', str(ail_root / 'ail_chatgpt.py'), *map(str, args)],
                                cwd=work, capture_output=True, timeout=900, env=env)
        if result.returncode:
            raise SystemExit('%s: ail_chatgpt %s failed:\n%s' % (label, args[0], result.stderr.decode(errors='replace')[-3000:]))
    if hasattr(app, 'prepare_ail'):
        app.prepare_ail(work, cli)
    out = work / label
    cli('compile', ail_root / app.AIL_SOURCE, *(o.replace('{work}', str(work)) for o in app.AIL_OPTIONS), '-o', out)
    return out


def build_reference(app, work, label, env=None):
    gcc, rustc = shutil.which('gcc'), shutil.which('rustc')
    source = work / (label + ('.c' if label == 'c' else '.rs'))
    source.write_text(app.C_SOURCE if label == 'c' else app.RUST_SOURCE, encoding='utf8')
    out = work / label
    command = [gcc, *C_FLAGS, str(source), '-lm', '-o', str(out)] if label == 'c' else [rustc, *RUST_FLAGS, str(source), '-o', str(out)]
    result = subprocess.run(command, capture_output=True, timeout=300, env=env)
    if result.returncode:
        raise SystemExit('%s reference build failed:\n%s' % (label, result.stderr.decode(errors='replace')[-3000:]))
    return out


def tree_kib(path):
    """Disk allocated under path, in KiB (what `du -sk` reports; hardlinks counted once)."""
    return int(subprocess.run(['du', '-sk', str(path)], capture_output=True, text=True, check=True).stdout.split()[0])


def build_disk_kib(app, base_root, work):
    """Disk one release build adds, per arm, in KiB. A separate pass after the timing, so it cannot disturb it.
    Each arm builds into a fresh directory with a fresh cache and TMPDIR, and the whole directory is counted:
    ail/base = AIL_CACHE + build dir (output binary, files prepare_ail makes); c, rust = build dir (output binary
    plus whatever gcc/rustc leave in TMPDIR). The harness calls rustc directly, so there is no cargo target/ dir."""
    result = {}
    for label in ('base', 'ail', 'c', 'rust'):
        if label == 'base' and not base_root:
            continue
        fresh = work / ('disk-' + label)
        (fresh / 'cache').mkdir(parents=True)
        (fresh / 'tmp').mkdir()
        env = dict(os.environ, AIL_CACHE=str(fresh / 'cache'), TMPDIR=str(fresh / 'tmp'), CARGO_TARGET_DIR=str(fresh / 'target'))
        env.pop('AIL_NO_CACHE', None)
        if label == 'c' or label == 'rust':
            build_reference(app, fresh, label, env)
        else:
            build_ail(app, base_root if label == 'base' else REPO / 'AIL_CURRENT', fresh, label, env)
        result[label] = tree_kib(fresh)
    return result


def toolchain_kib():
    """Install size once per language, `du -sk` of the toolchain's install dir (None if missing)."""
    def du(*paths):
        paths = [p for p in paths if p and Path(p).exists()]
        return sum(tree_kib(p) for p in dict.fromkeys(map(str, paths))) if paths else None
    sizes = {}
    gcc = shutil.which('gcc')
    if gcc:
        # system gcc lives in /usr, so count its own parts: driver, compiler proper + its lib dir, as, ld
        prog = lambda n: subprocess.run([gcc, '-print-prog-name=' + n], capture_output=True, text=True).stdout.strip()
        cc1 = os.path.realpath(prog('cc1'))
        sizes['c'] = du(os.path.realpath(gcc), os.path.dirname(cc1), os.path.realpath(prog('as')), os.path.realpath(prog('ld')))
    rustc = shutil.which('rustc')
    if rustc:
        sysroot = subprocess.run([rustc, '--print', 'sysroot'], capture_output=True, text=True).stdout.strip()
        sizes['rust'] = du(sysroot)   # ~/.rustup/toolchains/<active>
    sizes['ail'] = du(REPO / 'AIL_CURRENT')   # the compiler itself; it also needs the c toolchain above and python3
    return sizes


def run_case(binary, case, work):
    """Run once; return (elapsed_ns, problems)."""
    out = work / 'run.out'
    out.unlink(missing_ok=True)
    argv = [str(binary), *(a.replace('{out}', str(out)) for a in case['args'])]
    start = time.perf_counter_ns()
    process = subprocess.run(argv, capture_output=True, timeout=300)
    elapsed = time.perf_counter_ns() - start
    problems = []
    if case['expect_exit'] == 0:
        if process.returncode:
            problems.append('exit %d' % process.returncode)
        if process.stderr:
            problems.append('stderr on success')
    elif process.returncode == 0:
        problems.append('accepted a rejected case')
    if case.get('expected_stdout') is not None and process.stdout != case['expected_stdout']:
        problems.append('stdout differs')
    if case.get('stdout_empty') and process.stdout:
        problems.append('stdout on rejected case')
    if case.get('expected_file') is not None and (not out.is_file() or out.read_bytes() != case['expected_file']):
        problems.append('output file differs')
    out.unlink(missing_ok=True)
    return elapsed, problems


def peak_rss_kib(binary, case, work):
    telemetry, out = work / 'time.txt', work / 'run.out'
    out.unlink(missing_ok=True)
    subprocess.run(['/usr/bin/time', '-v', '-o', str(telemetry), '--', str(binary),
                    *(a.replace('{out}', str(out)) for a in case['args'])], capture_output=True, timeout=300)
    out.unlink(missing_ok=True)
    found = re.findall(r'Maximum resident set size \(kbytes\):\s*(\d+)', telemetry.read_text(errors='replace'))
    return int(found[0]) if found else None


def compare_app(name, base_root, work, rounds, smoke):
    app = load_app(name)
    arms = {}
    if base_root:
        arms['base'] = build_ail(app, base_root, work, 'base')
    arms['ail'] = build_ail(app, REPO / 'AIL_CURRENT', work, 'ail')
    arms['c'] = build_reference(app, work, 'c')
    arms['rust'] = build_reference(app, work, 'rust')
    failures = [(label, case['name'], problems) for case in app.controls(work) for label, binary in arms.items()
                for _, problems in [run_case(binary, case, work)] if problems]
    if failures:
        raise SystemExit('%s: boundary controls failed: %r' % (name, failures[:10]))
    case = app.generate(work, smoke)
    labels = list(arms)
    orders = list(itertools.permutations(labels))
    windows = []
    for w in range(1 if smoke else WINDOWS):
        sums = dict.fromkeys(labels, 0)
        for r in range(rounds):
            for label in orders[(w * rounds + r) % len(orders)]:
                elapsed, problems = run_case(arms[label], case, work)
                if problems:
                    raise SystemExit('%s: timed run of %s failed: %s' % (name, label, problems))
                sums[label] += elapsed
        windows.append(sums)
    disk = build_disk_kib(app, base_root, work)
    result = dict(app=name, case=case['name'], rounds=rounds, windows=windows,
                  median_ms={l: statistics.median(w[l] for w in windows) / rounds / 1e6 for l in labels},
                  peak_rss_kib={l: peak_rss_kib(b, case, work) for l, b in arms.items()},
                  build_disk_kib=disk,
                  binary_bytes={l: Path(b).stat().st_size for l, b in arms.items() if Path(b).exists()},
                  ratios={})
    for num, den in (('ail', 'base'), ('ail', 'c'), ('ail', 'rust')):
        if den in arms:
            values = sorted(w[num] / w[den] for w in windows)
            result['ratios'][num + '/' + den] = dict(median=statistics.median(values),
                                                     range=[values[1], values[-2]] if len(values) >= 9 else None)
    return result


def _fmt_bound(value):
    """Format a ratio at 3 decimals, adding digits until its side of 1.0 is preserved.

    Plain '%.3f' turns 0.9996 into 1.000, so a range entirely below 1.0 can print as
    [0.981, 1.000] and look like a tie although the unrounded bounds make the verdict faster.
    """
    digits = 3
    while True:
        text = '%.*f' % (digits, value)
        printed = float(text)
        if (printed < 1.0) == (value < 1.0) and (printed > 1.0) == (value > 1.0):
            return text
        digits += 1


def fmt(ratio):
    if ratio['range'] is None:
        return _fmt_bound(ratio['median'])
    lo, hi = ratio['range']
    verdict = 'tie' if lo <= 1 <= hi else ('faster' if hi < 1 else 'slower')
    return '%s [%s, %s] %s' % (_fmt_bound(ratio['median']), _fmt_bound(lo), _fmt_bound(hi), verdict)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--app', action='append', choices=APPS, help='repeatable; default: all apps')
    parser.add_argument('--base', default='HEAD', help="git revision for the AIL baseline arm, or 'none'")
    parser.add_argument('--rounds', type=int, default=16)
    parser.add_argument('--smoke', action='store_true', help='small inputs, one window: check the plumbing only')
    parser.add_argument('--cpu', type=int, default=1)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux only')
    os.sched_setaffinity(0, {args.cpu})
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain', 'AIL_CURRENT'], cwd=REPO, capture_output=True, text=True).stdout)
    base_tree = None
    results = []
    with tempfile.TemporaryDirectory(prefix='ail-bench-') as tmp:
        tmp = Path(tmp)
        if args.base != 'none':
            base_tree = tmp / 'base-tree'
            subprocess.run(['git', 'worktree', 'add', '--detach', str(base_tree), args.base], cwd=REPO,
                           check=True, capture_output=True)
        try:
            for name in args.app or APPS:
                work = tmp / name
                work.mkdir()
                print('running', name, file=sys.stderr, flush=True)
                results.append(compare_app(name, base_tree / 'AIL_CURRENT' if base_tree else None, work, args.rounds, args.smoke))
        finally:
            if base_tree:
                subprocess.run(['git', 'worktree', 'remove', '--force', str(base_tree)], cwd=REPO, capture_output=True)
    toolchain = toolchain_kib()
    report = dict(when=datetime.now(timezone.utc).isoformat(timespec='seconds'), head=head, working_tree_dirty=dirty,
                  base=args.base, smoke=args.smoke, toolchain_kib=toolchain, cpu=args.cpu, c_flags=C_FLAGS, rust_flags=RUST_FLAGS, results=results)
    if not args.smoke:
        out = REPO / 'bench/results' / ('%s-%s%s.json' % (report['when'][:10], head, '-dirty' if dirty else ''))
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=1) + '\n', encoding='utf8')
        print('wrote', out.relative_to(REPO), file=sys.stderr)
    columns = [c for c in ('ail/base', 'ail/c', 'ail/rust') if any(c in r['ratios'] for r in results)]
    # Speed is not the only cost: peak memory and binary size are printed beside it.
    print('| app | ms ail/base/c/rust | ' + ' | '.join(columns) + ' | RSS MiB ail/base/c/rust | binary KiB ail/base/c/rust | build disk KiB ail/base/c/rust |')
    print('|---|---|' + '---|' * len(columns) + '---|---|---|')
    for r in results:
        ms = '/'.join('%.1f' % r['median_ms'][l] if l in r['median_ms'] else '-' for l in ('ail', 'base', 'c', 'rust'))
        rss = '/'.join('%.1f' % (r['peak_rss_kib'][l] / 1024) if r['peak_rss_kib'].get(l) else '-' for l in ('ail', 'base', 'c', 'rust'))
        size = '/'.join('%d' % (r['binary_bytes'][l] // 1024) if l in r.get('binary_bytes', {}) else '-' for l in ('ail', 'base', 'c', 'rust'))
        disk = '/'.join('%d' % r['build_disk_kib'][l] if l in r['build_disk_kib'] else '-' for l in ('ail', 'base', 'c', 'rust'))
        print('| %s | %s | %s | %s | %s | %s |' % (r['app'], ms, ' | '.join(fmt(r['ratios'][c]) if c in r['ratios'] else '-' for c in columns), rss, size, disk))
    print('\ntoolchain KiB (du -sk, once per language): ' + ', '.join('%s %s' % (l, '%d' % k if k is not None else 'missing (skipped)') for l, k in toolchain.items()))


if __name__ == '__main__':
    main()
