"""fclist1: a list parameter the callee writes element by element is passed in place.

`pyfunc._scan_written_lists` proves that a callee only indexes, measures, iterates or forwards its
list parameter (stores only `xs[i] = v`, never resizes, keeps or returns it), and that every call
site passes caller-owned storage with no other list read in the same expression. Such a parameter
is a writable pointer into the caller's buffer, so the caller sees the stores as in CPython; any
other shape keeps the read-only refusal and the general path.

Every probe in `lab/reach/fclist1/` (aliasing: the same list twice, a grid row, a dict value,
`f(xs) is xs`, a global store, append while iterating, a name alias, a list of lists, an empty
list, negative indexes, ints at and beyond int64) and the three pyperf programs are built in the
default mode and with `AIL_UNIFIED_FORCE=1`; stdout and the exit status must equal CPython's, except
that an int64 overflow must stop loudly (exit 1, a message on stderr) where CPython promotes.
`nqueens.py` must also be on the typed path with a writable list parameter in its C.
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
PROBES = sorted((REPO / 'lab' / 'reach' / 'fclist1').glob('p*.py'))
PROGRAMS = [REPO / 'lab' / 'pyperf' / 'bench' / name
            for name in ('nqueens.py', 'scimark_fft.py', 'spectral_norm.py')]
ARGS = {'nqueens.py': ['7'], 'scimark_fft.py': ['64'], 'spectral_norm.py': ['40']}
# probes whose CPython output needs an int beyond int64: the build must stop loudly instead
OVERFLOW = {'p08_int64.py', 'p20_bigvalue_store.py'}
HAVE_CC = bool(shutil.which('cc') or shutil.which('gcc'))


def build(src, out, env_extra, debug_dir=None):
    env = dict(os.environ, **env_extra)
    cmd = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(src), '-o', str(out)]
    if debug_dir:
        cmd += ['--debug-dir', str(debug_dir)]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class WrittenListParams(unittest.TestCase):
    def check(self, src, mode_env):
        args = ARGS.get(src.name, [])
        want = run([sys.executable, str(src)] + args)
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'prog'
            built = build(src, exe, mode_env)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            got = run([str(exe)] + args)
        if src.name in OVERFLOW:
            self.assertEqual(got.returncode, 1, got.stdout + got.stderr)
            self.assertTrue(want.stdout.startswith(got.stdout), (got.stdout, want.stdout))
            self.assertTrue(got.stderr.strip(), 'the overflow stop must say why')
            return
        self.assertEqual((got.stdout, got.returncode), (want.stdout, want.returncode), src.name)

    def test_probes_and_programs(self):
        self.assertGreaterEqual(len(PROBES), 12)
        for mode, env in (('default', {}), ('force', {'AIL_UNIFIED_FORCE': '1'})):
            for src in PROBES + PROGRAMS:
                with self.subTest(mode=mode, program=src.name):
                    self.check(src, env)

    def test_nqueens_typed_in_place(self):
        src = PROGRAMS[0]
        with tempfile.TemporaryDirectory() as tmp:
            built = build(src, Path(tmp) / 'prog', {}, Path(tmp) / 'dbg')
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            self.assertNotIn('general path', built.stderr)
            c = (Path(tmp) / 'dbg' / 'program.c').read_text()
        self.assertIn('int64_t *v_cols, int64_t v_cols_len', c)
        self.assertNotIn('const int64_t *v_cols', c)


if __name__ == '__main__':
    unittest.main()
