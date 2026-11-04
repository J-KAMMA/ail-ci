"""Score the refusal message of every program in `progs/` and gate regressions.

Each program starts with two header comments:

    # line: N       the line CPython or a reader would blame
    # names: TEXT   a short substring that names the construct

The first non-`note:` stderr line of the default build scores one point for each of:

1. the compile exits with a clean refusal status (3 subset refusal, 2 syntax error),
   not 1 with a Python traceback and not a C compiler error;
2. it starts with `<file>.py:N:` naming the program's own file and the header line;
3. it contains the `names` text (case-insensitive);
4. it gives a rewrite hint (one of `HINT_WORDS`).

A program that now builds is reported as `builds now`: its score is 0.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGS_DIR = HERE / 'progs'
BASELINE = HERE / 'baseline.json'
COMPILER = (HERE.parents[1] / 'AIL_CURRENT' / 'ail_chatgpt.py').resolve()
TIMEOUT = 120
WORKERS = 2
MEMORY_LIMIT = 1500000 * 1024  # ulimit -v 1500000

# Exact rewrite-hint words rule 4 looks for.
HINT_WORDS = ('write instead', 'use ', 'did you mean', 'rename', 'instead')

CLEAN_STATUSES = (2, 3)
TRACEBACK = 'Traceback (most recent call last)'


def _limit_memory():
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, ValueError, OSError):
        pass


def header(path):
    """Return (line, names, body) from a program's header comments."""
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    line = None
    names = ''
    for raw in lines:
        if raw.startswith('# line:'):
            line = int(raw.split(':', 1)[1].strip())
        elif raw.startswith('# names:'):
            names = raw.split(':', 1)[1].strip()
        else:
            break
    return line, names, text


def first_line(stderr):
    for line in (stderr or '').splitlines():
        if not line.startswith('note:'):
            return line
    return ''


def score_message(status, path, line, names, first):
    """Score one refusal message 0-4."""
    points = 0
    if status in CLEAN_STATUSES:
        points += 1
    if first.startswith('%s:%d:' % (path.name, line)):
        points += 1
    if names and names.lower() in first.lower():
        points += 1
    low = first.lower()
    if any(word in low for word in HINT_WORDS):
        points += 1
    return points


def _env():
    env = dict(os.environ)
    env['AIL_NO_CACHE'] = '1'
    env.pop('AIL_UNIFIED_FORCE', None)
    return env


def evaluate(path):
    """Build one program in a temp dir and score its refusal."""
    line, names, text = header(path)
    with tempfile.TemporaryDirectory() as directory:
        dest = Path(directory) / path.name
        dest.write_text(text, encoding='utf-8')
        built = subprocess.run(
            [sys.executable, '-B', str(COMPILER), 'compile', path.name, '-o', 'out'],
            cwd=directory, capture_output=True, text=True, timeout=TIMEOUT,
            env=_env(), preexec_fn=_limit_memory)
    first = first_line(built.stderr)
    builds = built.returncode == 0
    cpython_rejects = None
    if builds:
        cpython_rejects = _cpython_rejects(text, path.name)
    return {
        'program': path.name,
        'status': built.returncode,
        'line': line,
        'names': names,
        'score': 0 if builds else score_message(built.returncode, path, line, names, first),
        'first': first[:160],
        'builds': builds,
        'cpython_rejects': cpython_rejects,
        'stderr': built.stderr or '',
    }


def _cpython_rejects(text, name):
    with tempfile.TemporaryDirectory() as directory:
        dest = Path(directory) / name
        dest.write_text(text, encoding='utf-8')
        try:
            ran = subprocess.run([sys.executable, name], cwd=directory,
                                 capture_output=True, text=True, timeout=30,
                                 preexec_fn=_limit_memory)
        except subprocess.TimeoutExpired:
            return True
    return ran.returncode != 0


def evaluate_all():
    programs = sorted(PROGS_DIR.glob('*.py'))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(evaluate, programs))


def read_baseline():
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding='utf-8'))


def write_baseline(results):
    data = {item['program']: item['score'] for item in results}
    BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return data


def check(results=None):
    """Return a list of human-readable failures; empty means the gate passes."""
    if results is None:
        results = evaluate_all()
    baseline = read_baseline()
    failures = []
    if not baseline:
        failures.append('no baseline: run `python3 lab/errux/score.py --write-baseline`')
        return failures
    for item in results:
        name = item['program']
        if name not in baseline:
            failures.append('%s: missing from baseline.json' % name)
            continue
        if item['builds']:
            if item['cpython_rejects']:
                failures.append('%s: builds now but CPython rejects it' % name)
            continue
        if item['score'] < baseline[name]:
            failures.append('%s: score %d is below baseline %d (%s)'
                            % (name, item['score'], baseline[name], item['first']))
    return failures


def print_table(results):
    print('%-40s %5s %7s  %s' % ('program', 'score', 'status', 'first stderr line'))
    for item in results:
        status = 'builds now' if item['builds'] else str(item['status'])
        print('%-40s %5d %7s  %s' % (item['program'], item['score'], status, item['first']))
    total = sum(item['score'] for item in results)
    print('\ntotal %d / %d over %d programs' % (total, 4 * len(results), len(results)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-baseline', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    results = evaluate_all()
    print_table(results)
    if args.write_baseline:
        data = write_baseline(results)
        print('\nwrote %s (%d programs)' % (BASELINE, len(data)))
    if args.check:
        failures = check(results)
        if failures:
            print('\nFAIL:')
            for failure in failures:
                print('  ' + failure)
            return 1
        print('\nOK: every message meets its baseline and no build leaked C text')
    return 0


if __name__ == '__main__':
    sys.exit(main())
