#!/usr/bin/env python3
"""Peak RSS after every op-prefix of the tree_fold performance input.

    python3 tools/rss_phases.py /tmp/tf_ail
    python3 tools/rss_phases.py --n 3000000 /tmp/tf_ail /tmp/tf_c

The input is gen.random_tree(random.Random(1), N, chain=0.35) plus the 17 perf ops from gen.cases().
For every prefix (parse only, then one more op at a time) the binary is run under RLIMIT_AS with
/usr/bin/time -f %M, once with the default glibc and once with
GLIBC_TUNABLES=glibc.malloc.mmap_threshold=131072.  Peak RSS is reported in MiB.

This is a diagnostic, not a verdict: glibc keeps freed brk-heap memory resident, so the default
column can stay high after a phase whose own live set is much smaller.
"""
import argparse, importlib.util, os, re, shlex, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PERF_OPS = ['stats', 'total', 'level 6', 'find leaf', 'sort', 'find qqqqqqqqqqqqqqqq', 'prune 40', 'stats',
            'fold', 'stats', 'cut mid', 'mirror', 'level 3', 'find x+y', 'sort', 'stats', 'print']
MODES = (('default', {}), ('fixed', {'GLIBC_TUNABLES': 'glibc.malloc.mmap_threshold=131072'}))


def gen():
    path = REPO / 'lab' / 'compare' / 'tasks' / 'tree_fold' / 'gen.py'
    spec = importlib.util.spec_from_file_location('tree_fold_gen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prefixes(n):
    import random
    module = gen()
    tree = module.random_tree(random.Random(1), n, chain=0.35)
    lines = module.doc(tree, *PERF_OPS, final=False).split(b'\n')
    for k in range(len(lines)):
        yield k, (PERF_OPS[k - 1] if k else 'parse'), b'\n'.join(lines[:k + 1]) + b'\n'


def peak_kib(binary, data, limit_kib, extra_env, timeout):
    env = dict(os.environ)
    env.pop('GLIBC_TUNABLES', None)
    env.update(extra_env)
    with tempfile.NamedTemporaryFile(prefix='rss-phases-', delete=False) as handle:
        time_file = handle.name
    script = 'ulimit -v %d; exec /usr/bin/time -f %%M -o %s -- %s' % (
        limit_kib, shlex.quote(time_file), shlex.quote(str(binary)))
    try:
        done = subprocess.run(['/bin/sh', '-c', script],
                              input=data, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              env=env, timeout=timeout)
        text = Path(time_file).read_text(errors='replace')
        match = re.search(r'^\s*(\d+)\s*$', text, re.M)
        if done.returncode != 0 or not match:
            tail = done.stderr.decode('utf8', 'replace').strip().splitlines()[-1:] or ['no RSS']
            return None, 'exit %d: %s' % (done.returncode, tail[0])
        return int(match.group(1)), None
    except subprocess.TimeoutExpired:
        return None, 'timeout after %ss' % timeout
    finally:
        Path(time_file).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('binaries', nargs='+', type=Path, help='tree_fold binaries to measure')
    parser.add_argument('--n', type=int, default=1000000, help='tree size (default: 1000000)')
    parser.add_argument('--limit-mb', type=int, default=1500, help='RLIMIT_AS in MiB (default: 1500)')
    parser.add_argument('--timeout', type=int, default=900, help='seconds per run (default: 900)')
    args = parser.parse_args()
    for binary in args.binaries:
        if not binary.is_file():
            parser.error('not a file: %s' % binary)
    print('tree_fold prefixes, N=%d, RLIMIT_AS=%d MiB, peak RSS in MiB' % (args.n, args.limit_mb))
    for binary in args.binaries:
        print('%s:' % binary)
        values = {name: [] for name, _ in MODES}
        failures = []
        for k, op, data in prefixes(args.n):
            row = []
            for name, env in MODES:
                kib, error = peak_kib(binary, data, args.limit_mb * 1024, env, args.timeout)
                values[name].append(kib)
                row.append('%7s' % ('-' if kib is None else '%.1f' % (kib / 1024.0)))
                if error:
                    failures.append('%s/%s: %s' % (name, op, error))
            print('  %2d %-22s default %s   fixed %s' % (k, op, row[0], row[1]))
        best = {name: max((v for v in values[name] if v is not None), default=None) for name, _ in MODES}
        print('  peak: default %s MiB, fixed %s MiB' % tuple('-' if best[m] is None else '%.1f' % (best[m] / 1024.0)
                                                             for m, _ in MODES))
        for failure in failures:
            print('  failed %s' % failure)
    return 0


if __name__ == '__main__':
    sys.exit(main())
