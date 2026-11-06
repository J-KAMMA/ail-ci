#!/usr/bin/env python3
"""Run the 12 lab/asyncio programs on the generator-only model.

    python3 lab/asyncio/model/run_model.py            # compare the model with expected/
    python3 lab/asyncio/model/run_model.py --capture  # rewrite expected/ from CPython
    python3 lab/asyncio/model/run_model.py --oracle   # compare expected/ with CPython

An expected file is the program's stdout followed by one final line `exit: N`.
`--capture` never uses the model: it records CPython 3.12 (`python3` on PATH is
checked to be 3.12) as the oracle.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPECTED = ROOT / 'expected'


def transcript(process):
    text = process.stdout.decode('utf-8', 'replace')
    if text and not text.endswith('\n'):
        text += '\n'
    return text + 'exit: %d\n' % process.returncode


def run(program, use_model):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if use_model:
        env['PYTHONPATH'] = str(HERE)
    env.setdefault('AIL_CLOCK', '1700000000')
    process = subprocess.run([sys.executable, str(program)], cwd=str(ROOT), env=env,
                             capture_output=True, timeout=60)
    return transcript(process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true', help='record expected/ from CPython')
    parser.add_argument('--oracle', action='store_true', help='compare expected/ with CPython only')
    args = parser.parse_args()

    if args.capture:
        if sys.version_info[:2] != (3, 12):
            parser.error('the oracle must be CPython 3.12 (this is %d.%d)' % sys.version_info[:2])
        EXPECTED.mkdir(parents=True, exist_ok=True)

    programs = sorted(ROOT.glob('l*.py'))
    if len(programs) != 12:
        parser.error('expected 12 lab/asyncio/l*.py programs, found %d' % len(programs))

    failures = 0
    for program in programs:
        target = EXPECTED / (program.stem + '.txt')
        if args.capture:
            target.write_text(run(program, use_model=False), encoding='utf-8')
            print('captured', target.relative_to(ROOT))
            continue
        want = target.read_text(encoding='utf-8')
        if args.oracle:
            got = run(program, use_model=False)
            label = 'CPython'
        else:
            got = run(program, use_model=True)
            label = 'model'
        if got != want:
            failures += 1
            print('FAIL %s (%s)' % (program.name, label))
            for index, (left, right) in enumerate(zip(want.splitlines(), got.splitlines()), 1):
                if left != right:
                    print('  line %d: expected %r, got %r' % (index, left, right))
                    break
            if len(want.splitlines()) != len(got.splitlines()):
                print('  line count: expected %d, got %d'
                      % (len(want.splitlines()), len(got.splitlines())))
        else:
            print('ok', program.name, '(%s)' % label)

    if failures:
        print('%d/%d failed' % (failures, len(programs)))
        return 1
    print('%d/%d matched' % (len(programs), len(programs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
