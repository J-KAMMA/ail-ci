#!/usr/bin/env python3
"""Run the platform subset of the AIL test suite on Windows, macOS and Linux arm64.

    python3 lab/platforms/run.py --platform windows --shard 0 --shards 3 -j 4
    python3 lab/platforms/run.py --platform macos --all --shard 2 --shards 6
    python3 lab/platforms/run.py --platform windows --list          # modules this platform runs

lab/platforms/config.json says which modules form the representative set and which modules or
single tests are skipped on which platform, each with the reason. A skip is a statement about the
test, never about the compiler: every entry says what the test assumes (a POSIX shell, `ulimit`,
signals, a byte-exact LF newline, a Linux-only allocator hook, ...).

Each module runs in its own interpreter (`python -X utf8 -B -m unittest`-equivalent) so one hung
or crashing module cannot take the others down. Tests that compare program output byte for byte
with an LF newline cannot hold on Windows, where text-mode stdout writes CRLF as CPython does;
those are skipped there by name (the CRLF-aware ones run).

Nothing here changes the compiler: the private tree is synced by export.py and only this lab
directory and .github/workflows/platforms.yml belong to the platform CI repository.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONFIG = HERE / 'config.json'


def child(module, skip):
    root = REPO / 'AIL_CURRENT'
    os.chdir(root)
    sys.path.insert(0, str(root))
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    def walk(item):
        if isinstance(item, unittest.TestSuite):
            for sub in item:
                walk(sub)
        elif item.id().split('.')[-1].split(' ')[0] in skip:
            return
        else:
            suite.addTest(item)

    walk(loader.loadTestsFromName(module))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def selection(config, platform, everything):
    sys.path.insert(0, str(REPO / 'AIL_CURRENT'))
    import ail_check
    available = list(ail_check.MODULES)
    exists = lambda m: (REPO / 'AIL_CURRENT' / (m + '.py')).is_file()
    chosen = available if everything else [m for m in config['representative'] if exists(m)]
    missing = [m for m in config['representative'] if not exists(m)]
    skips = config['skip']
    run, skipped, partial = [], [], {}
    for module in sorted(chosen):
        entry = skips.get(module, {})
        if platform in entry.get('modules', {}):
            skipped.append((module, entry['modules'][platform]))
            continue
        tests = {name for name, platforms in entry.get('tests', {}).items() if platform in platforms}
        if tests:
            partial[module] = sorted(tests)
        run.append(module)
    return run, skipped, partial, missing


def run_module(module, skip, timeout, env):
    start = time.monotonic()
    command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), '--child', module]
    if skip:
        command += ['--skip', ','.join(skip)]
    try:
        proc = subprocess.run(command, cwd=REPO / 'AIL_CURRENT', env=env, capture_output=True, text=True,
                              encoding='utf8', errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        return module, 124, time.monotonic() - start, 'timed out after %ss' % timeout
    return module, proc.returncode, time.monotonic() - start, proc.stdout + proc.stderr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=('windows', 'macos', 'linux-arm64', 'linux'))
    parser.add_argument('--all', action='store_true', help='every ail_check module, not only the representative set')
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('-j', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=1500)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--only', default='', help='comma separated module names to run (debugging)')
    parser.add_argument('--child')
    parser.add_argument('--skip', default='')
    parser.add_argument('--no-preflight', action='store_true')
    args = parser.parse_args()
    if args.child:
        return child(args.child, set(filter(None, args.skip.split(','))))
    if not args.platform:
        parser.error('--platform is required')
    config = json.loads(CONFIG.read_text(encoding='utf8'))
    run, skipped, partial, missing = selection(config, args.platform, args.all)
    weights = config.get('weights', {})
    run.sort(key=lambda m: (-weights.get(m, 30), m))
    if args.only:
        run = [m for m in run if m in args.only.split(',')]
    mine = run[args.shard::args.shards]   # round robin over modules sorted by weight: balanced shards
    if args.list:
        print('\n'.join(mine))
        return 0
    os.chdir(REPO / 'AIL_CURRENT')
    sys.path.insert(0, str(REPO / 'AIL_CURRENT'))
    import ail_check
    if not args.no_preflight:
        ail_check.preflight(REPO / 'AIL_CURRENT')
    env = dict(os.environ, PYTHONUTF8='1')
    print('platform %s shard %d/%d: %d modules (%d skipped for this platform, %d with skipped tests)'
          % (args.platform, args.shard, args.shards, len(mine), len([s for s in skipped]), len(partial)), flush=True)
    for module, reason in skipped:
        print('SKIP module %s: %s' % (module, reason))
    for module, tests in partial.items():
        for name in tests:
            print('SKIP test %s.%s: %s' % (module, name, config['skip'][module]['tests'][name][args.platform]))
    for module in missing:
        print('NOTE %s is in the representative list but the file is missing' % module)
    failed = []
    start = time.monotonic()
    with ThreadPoolExecutor(args.j) as pool:
        futures = [pool.submit(run_module, m, partial.get(m, ()), args.timeout, env) for m in mine]
        for done, future in enumerate(as_completed(futures), 1):
            module, code, seconds, output = future.result()
            if code:
                failed.append(module)
                print('FAIL %s (%.0fs)\n%s' % (module, seconds, output[-6000:]), flush=True)
            else:
                print('ok   %-52s %6.1fs  [%d/%d]' % (module, seconds, done, len(mine)), flush=True)
    summary = '%s shard %d/%d: %d modules in %.0fs, %d failed%s' % (
        args.platform, args.shard, args.shards, len(mine), time.monotonic() - start, len(failed),
        ': ' + ' '.join(failed) if failed else '')
    print(summary)
    target = os.environ.get('GITHUB_STEP_SUMMARY')
    if target:
        with open(target, 'a', encoding='utf8') as out:
            out.write('### %s\n\n' % summary)
            for module, reason in skipped:
                out.write('- skipped `%s`: %s\n' % (module, reason))
            for module, tests in partial.items():
                for name in tests:
                    out.write('- skipped test `%s.%s`: %s\n' % (module, name, config['skip'][module]['tests'][name][args.platform]))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
