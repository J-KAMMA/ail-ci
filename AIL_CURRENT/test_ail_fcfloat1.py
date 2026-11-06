"""fcfloat1: written list[float] parameters and nested-list parameters inferred from call sites.

fclist1 passes an element-written list parameter in place; with callinf1's call-site kinds a
list[float] parameter takes the same route (its `ail_flist` shares the caller's buffer, stores are
bounds-checked and never resize). `nested_lists.NestedLists.infer_params` makes an unannotated
parameter that every plain call hands the same `list[list[T]]` local that nested list, so
`bi = bodies[i]; bi[3] = ...` writes the caller's row (nbody).

Every probe in `lab/reach/fcfloat1/` (the same list twice, a name alias, NaN and inf, -0.0, an int
stored into a float list or row, an empty list, negative indexes and IndexError, row aliases, two
nested kinds at the call sites, a shared row, an int grid, appends through the parameter, a
rebound parameter, a module-level call, operand order) and the three pyperf programs are built in
the default mode and with `AIL_UNIFIED_FORCE=1`; stdout and exit status must equal CPython's
(floats are printed with repr). The three pyperf programs must be on the typed path.
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
PROBES = sorted((REPO / 'lab' / 'reach' / 'fcfloat1').glob('p*.py'))
PROGRAMS = [REPO / 'lab' / 'pyperf' / 'bench' / name
            for name in ('nbody.py', 'scimark_fft.py', 'spectral_norm.py')]
ARGS = {'nbody.py': ['100'], 'scimark_fft.py': ['64'], 'spectral_norm.py': ['40']}
TYPED_PROBES = {'p10_nest_twice.py', 'p12_int_grid.py', 'p13_row_append.py'}
HAVE_CC = bool(shutil.which('cc') or shutil.which('gcc'))


def build(src, out, env_extra):
    env = dict(os.environ, **env_extra)
    cmd = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(src), '-o', str(out)]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class FloatAndNestedParams(unittest.TestCase):
    def check(self, src, mode, mode_env):
        args = ARGS.get(src.name, [])
        want = run([sys.executable, str(src)] + args)
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'prog'
            built = build(src, exe, mode_env)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            if mode == 'default' and (src in PROGRAMS or src.name in TYPED_PROBES):
                self.assertNotIn('general path', built.stderr, src.name)
            got = run([str(exe)] + args)
        self.assertEqual((got.stdout, got.returncode), (want.stdout, want.returncode), src.name)

    def test_probes_and_programs(self):
        self.assertGreaterEqual(len(PROBES), 17)
        for mode, env in (('default', {}), ('force', {'AIL_UNIFIED_FORCE': '1'})):
            for src in PROBES + PROGRAMS:
                with self.subTest(mode=mode, program=src.name):
                    self.check(src, mode, env)


if __name__ == '__main__':
    unittest.main()
