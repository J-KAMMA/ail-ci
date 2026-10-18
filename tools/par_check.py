"""Run AIL_CURRENT/ail_check.py's suite in parallel:  python3 tools/par_check.py [-j 8] [MODULE ...]

Same preflight (pins, gcc, doctor) and the same module list as ail_check.py, but each test module
runs in its own `python -m unittest` process, 8 at a time by default, longest first (durations from the last
run are kept in ~/.cache/ail_par_check.json). The sequential suite took 11-28 minutes on a 16-core
machine; this is what to run while iterating. ail_check.py stays the reference (CI runs it).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'AIL_CURRENT'
TIMES = Path.home() / '.cache' / 'ail_par_check.json'


def run_module(name, env, timeout=None):
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', '-q', name],
                              cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf8',
                              errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, 124, time.monotonic() - start, 'timed out after %ss' % timeout
    return name, proc.returncode, time.monotonic() - start, proc.stdout + proc.stderr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-j', type=int, default=8)
    parser.add_argument('--timeout', type=float, default=None, help='seconds per module (default: none)')
    parser.add_argument('modules', nargs='*')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import ail_check
    ail_check.preflight(ROOT)
    modules = args.modules or list(ail_check.MODULES)
    try:
        times = json.loads(TIMES.read_text())
    except (OSError, ValueError):
        times = {}
    modules.sort(key=lambda m: -times.get(m, 60.0))
    env = dict(os.environ, PYTHONUTF8='1')
    env.setdefault('PIPE_CC', shutil.which('gcc') or '')
    start = time.monotonic()
    failed = []
    with ThreadPoolExecutor(args.j) as pool:
        futures = [pool.submit(run_module, m, env, args.timeout) for m in modules]
        for done, future in enumerate(as_completed(futures), 1):
            name, code, seconds, output = future.result()
            times[name] = round(seconds, 1)
            if code:
                failed.append(name)
                print('FAIL %s (%.0fs)\n%s' % (name, seconds, output[-4000:]), flush=True)
            else:
                print('ok   %-55s %6.1fs  [%d/%d]' % (name, seconds, done, len(modules)), flush=True)
    TIMES.parent.mkdir(parents=True, exist_ok=True)
    TIMES.write_text(json.dumps(times, indent=0, sort_keys=True))
    print('%d modules in %.0fs, %d failed%s' % (len(modules), time.monotonic() - start, len(failed),
                                               ': ' + ' '.join(failed) if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
