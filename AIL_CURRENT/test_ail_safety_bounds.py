"""Ratchet for the bounds-safety table: every program that matched CPython in the default and
general builds must keep matching (stdout, exit status and last stderr line).

The selected programs are the rows of lab/safety/bounds/RESULTS.md whose default and general
cells are `match`.  The programs are built again here, so a regression in either path fails.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BOUNDS = REPO / 'lab' / 'safety' / 'bounds'
CLI = ROOT / 'ail_chatgpt.py'
RESULTS = BOUNDS / 'RESULTS.md'
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
MEMORY_KB = 1_500_000
RUN_TIMEOUT = 20


def selected_programs():
    programs = []
    if not RESULTS.is_file():
        return programs
    for line in RESULTS.read_text(encoding='utf-8').splitlines():
        if not (line.startswith('| p') and line.rstrip().endswith('|')):
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) >= 5 and cells[2] == 'match' and cells[3] == 'match':
            programs.append(BOUNDS / cells[0])
    return programs


def build_env(general):
    env = dict(os.environ, AIL_NO_CACHE='1')
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return env


def run_limited(command, cwd, timeout=RUN_TIMEOUT):
    wrapped = ['bash', '-c',
               f'ulimit -v {MEMORY_KB} 2>/dev/null; exec timeout {timeout} "$@"', 'bash'] + \
              [str(part) for part in command]
    try:
        proc = subprocess.run(wrapped, cwd=cwd, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout + 15)
        timed_out = proc.returncode == 124
        return proc.returncode, proc.stdout, proc.stderr, timed_out
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or b'', exc.stderr or b'', True


def last_line(stderr):
    lines = [line for line in stderr.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class BoundsSafetyRatchet(unittest.TestCase):
    def test_default_and_general_still_match(self):
        programs = selected_programs()
        self.assertTrue(programs, f'no match rows found in {RESULTS}')
        with tempfile.TemporaryDirectory(prefix='ail-bounds-ratchet-') as tmp:
            for prog in programs:
                cpy_rc, cpy_out, cpy_err, cpy_timeout = run_limited([sys.executable, str(prog)], BOUNDS)
                self.assertFalse(cpy_timeout, prog.name)
                for mode in ('default', 'general'):
                    with self.subTest(program=prog.name, mode=mode):
                        out = Path(tmp) / f'{prog.stem}-{mode}'
                        built = subprocess.run(
                            [sys.executable, '-B', str(CLI), 'compile', str(prog), '-o', str(out)],
                            cwd=BOUNDS, capture_output=True, text=True, timeout=600,
                            env=build_env(mode == 'general'))
                        self.assertEqual(built.returncode, 0, built.stderr[-2000:])
                        self.assertTrue(out.is_file(), out)
                        rc, stdout, stderr, timed_out = run_limited([str(out)], BOUNDS)
                        self.assertFalse(timed_out, f'{prog.name} {mode}: timeout')
                        self.assertEqual(stdout, cpy_out, f'{prog.name} {mode}: stdout')
                        self.assertEqual(rc, cpy_rc, f'{prog.name} {mode}: exit status')
                        self.assertEqual(last_line(stderr), last_line(cpy_err),
                                         f'{prog.name} {mode}: last stderr line')


if __name__ == '__main__':
    unittest.main()
