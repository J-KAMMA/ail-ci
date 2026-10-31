"""A C function the generated program calls must be declared: an implicit declaration is a silent wrong value.

An implicitly declared C function returns ``int``.  When the runtime piece a program needs is referenced but
its definition is not emitted, gcc only warns (``implicit declaration of function``) and the program still
builds; a call that really runs then reads a garbage ``int`` where a ``double`` or a pointer was returned.

Found on integ: this three-line program built "passed" while gcc warned about ``ail__math_double``::

    def g(d):
        return {k: getattr(v, 'x') for k, v in d.items()}
    print(1)

``ail__math_double`` was defined only in the big-int world of cruntime.py (``/*B<*/ ... /*B|*/ ...
/*B>*/``), while the ``AIL_MATH_DBL`` macro used by every ``ail_math_*`` runtime function sits outside the
block; a program that cannot create a big int (the other world) therefore had the macro and no function.

Two guards, both tested here:

* the definition exists in both worlds of the size gate (``test_runtime_worlds_*``);
* every C compile of a generated program passes ``pipeline.STRICT_DECL_FLAGS`` (implicit function
  declaration, implicit int and incompatible pointer types are errors), so a future missing piece fails the
  build loudly (``test_flags_*``), and a scan of a set of programs finds no such diagnostic even when it is
  re-checked on the kept C source with an independent gcc call (``test_scan_*``).

Run as a script, it scans any number of programs (the full scan of lab/corpus, lab/compare, lab/syntax and
language_examples used to find the other missing pieces):

    python3 test_ail_no_implicit_decl.py --scan -j 2 FILE_OR_DIR...  [--root TREE] [--warn-baseline]

``--warn-baseline`` adds the strict flags through AIL_EXTRA_CFLAGS, to count the builds that had such a
warning in a tree that does not have the flags built in.
"""
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'python' / 'pkg-v12'))

STRICT = ['-Werror=implicit-function-declaration', '-Werror=implicit-int', '-Werror=incompatible-pointer-types']
DIAG = re.compile(r'implicit declaration of function|implicit-function-declaration|-Wimplicit-int|'
                  r'incompatible-pointer-types|incompatible pointer type|type defaults to .int')
CC = shutil.which('cc') or shutil.which('gcc')


def build(src, out, root=HERE, extra_env=None, debug_dir=None, timeout=600):
    """Compile one program; returns (returncode, text)."""
    src = Path(src).resolve()
    cmd = [sys.executable, '-B', str(Path(root).resolve() / "ail_chatgpt.py"), 'compile']
    if src.suffix == '.py':
        cmd += ['--syntax', 'python']
    if debug_dir:
        cmd += ['--debug-dir', str(debug_dir)]
    cmd += ['-o', str(out), str(src)]
    env = dict(os.environ, AIL_NO_CACHE='1', **(extra_env or {}))

    def limit():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (3 << 30, 3 << 30))
        except (ImportError, ValueError, OSError):
            pass
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout,
                           preexec_fn=limit if os.name == 'posix' else None, cwd=str(src.parent))
    except subprocess.TimeoutExpired:
        return -9, 'timeout'
    return r.returncode, (r.stdout + r.stderr)


def syntax_check(c_file):
    """gcc on the kept C source with the strict flags written out here, independent of the pipeline's own."""
    r = subprocess.run([CC, '-O0', '-fsyntax-only', *STRICT, str(c_file)], capture_output=True, text=True)
    return r.returncode, r.stderr


def scan_one(path, root=HERE, warn_baseline=False, keep=False):
    with tempfile.TemporaryDirectory(prefix='ail-implicit-') as d:
        out = Path(d) / 'prog'
        env = {'AIL_EXTRA_CFLAGS': ' '.join(STRICT)} if warn_baseline else None
        code, text = build(path, out, root, env, debug_dir=Path(d) / 'dbg' if keep else None)
        if code == 0:
            status = 'ok'
            if keep:
                c = Path(d) / 'dbg' / 'program.c'
                if c.exists():
                    sc, st = syntax_check(c)
                    if sc:
                        status, text = 'implicit', st
        elif DIAG.search(text):
            status = 'implicit'
        else:
            status = 'refused'
        return str(path), status, text


def collect(paths):
    files = []
    for p in (Path(q).resolve() for q in paths):
        if p.is_dir():
            files += sorted(q for q in p.rglob('*') if q.suffix in ('.py', '.ail') and q.name != '__init__.py')
        else:
            files.append(p)
    return files


class Programs(unittest.TestCase):
    MATH = '''import math

class P:
    def __init__(self, x):
        self.x = x

def g(d):
    return {k: getattr(v, 'x') for k, v in d.items()}

def apply(fn, v):
    return fn(v)

vals = g({'a': P(4), 'b': P(2.25), 'c': P(9)})
print(vals)
for name in ['a', 'b', 'c']:
    v = vals[name]
    for fn in [math.sqrt, math.fabs, math.exp, math.sin, math.cos, math.tan, math.log, math.floor,
               math.degrees, math.radians, math.isfinite, math.isnan]:
        print(name, apply(fn, v))
    print(math.hypot(v, 2), math.atan2(v, 3), math.copysign(v, -1), math.pow(v, 2))
'''
    REPRO = '''def g(d):
    return {k: getattr(v, 'x') for k, v in d.items()}
print(1)
'''

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix='ail-implicit-t-')
        self.addCleanup(self.dir.cleanup)
        self.tmp = Path(self.dir.name)

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding='utf-8')
        return p

    def test_runtime_worlds_define_math_double(self):
        import cruntime
        import biggate
        text = cruntime.OBJ2_COND
        # both sides of the block holding the big definition define it
        blocks = [m for m in biggate._BLOCK.finditer(text) if 'ail__math_double' in m.group(0)]
        self.assertTrue(blocks)
        for m in blocks:
            self.assertIn('ail__math_double', m.group(1))
            self.assertIn('ail__math_double', m.group(2))

    def test_flags_are_in_every_generated_compile(self):
        import pipeline
        import pyc
        self.assertEqual(list(pipeline.STRICT_DECL_FLAGS), STRICT)
        for flag in STRICT:
            self.assertIn(flag, pyc.CFLAGS_TUNE)
        for name in ('module_object.py', 'c_api.py', 'build_app.py', 'build_py.py'):
            self.assertIn('STRICT_DECL_FLAGS', (HERE / 'python' / 'pkg-v12' / name).read_text(encoding='utf-8'), name)

    @unittest.skipUnless(CC, 'no C compiler')
    def test_scan_repro_builds_without_diagnostics(self):
        for name, text in (('repro.py', self.REPRO), ('math_general.py', self.MATH)):
            path = self.write(name, text)
            p, status, out = scan_one(path, keep=True)
            self.assertEqual(status, 'ok', out[-1500:])

    @unittest.skipUnless(CC, 'no C compiler')
    def test_math_general_matches_cpython(self):
        path = self.write('m.py', self.MATH)
        expected = subprocess.run([sys.executable, str(path)], capture_output=True, text=True).stdout
        for force in (None, '1'):
            out = self.tmp / ('m_%s' % force)
            code, text = build(path, out, extra_env={'AIL_UNIFIED_FORCE': force} if force else None)
            self.assertEqual(code, 0, text[-1500:])
            run = subprocess.run([str(out)], capture_output=True, text=True)
            self.assertEqual((run.returncode, run.stdout), (0, expected), 'force=%s' % force)

    @unittest.skipUnless(CC, 'no C compiler')
    def test_a_missing_piece_fails_the_check(self):
        # a C source calling a function nothing declares: the strict flags turn gcc's warning into an error
        c = self.write('bad.c', 'static double f(void) { return 1.0; }\n'
                                'int main(void) { double d = missing_piece(1); return (int)(d + f()); }\n')
        code, err = syntax_check(c)
        self.assertNotEqual(code, 0)
        self.assertIn('implicit', err)

    @unittest.skipUnless(CC, 'no C compiler')
    def test_scan_example_set(self):
        # a spread of the repository's own programs: language examples, two compare-lab tasks in both syntaxes
        repo = HERE.parent
        picks = sorted((HERE / 'language_examples').glob('*.ail'))[::90]
        for task in ('tree_fold', 'tally_lang'):
            for fn in ('main.ail', 'main.py'):
                p = repo / 'lab' / 'compare' / 'src' / task / fn
                if p.exists():
                    picks.append(p)
        self.assertTrue(picks)
        bad = []
        for p in picks:
            _, status, out = scan_one(p, keep=True)
            if status == 'implicit':
                bad.append((p.name, out[-400:]))
        self.assertEqual(bad, [])


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('-j', type=int, default=2)
    ap.add_argument('--root', default=str(HERE))
    ap.add_argument('--warn-baseline', action='store_true')
    ap.add_argument('--keep', action='store_true', help='also re-check the kept C source with an independent gcc call')
    ap.add_argument('paths', nargs='+')
    a = ap.parse_args(argv)
    files = collect(a.paths)
    counts = {'ok': 0, 'refused': 0, 'implicit': 0}
    with concurrent.futures.ThreadPoolExecutor(a.j) as ex:
        futs = [ex.submit(scan_one, f, a.root, a.warn_baseline, a.keep) for f in files]
        for fut in futs:
            path, status, text = fut.result()
            counts[status] += 1
            if status == 'implicit':
                lines = [l for l in text.splitlines() if DIAG.search(l)][:2]
                print('IMPLICIT', path, ' | '.join(l.strip()[:200] for l in lines), flush=True)
    print('scanned %d: %s' % (len(files), counts))
    return 1 if counts['implicit'] else 0


if __name__ == '__main__':
    if '--scan' in sys.argv:
        sys.argv.remove('--scan')
        sys.exit(main(sys.argv[1:] + ['--scan']))
    unittest.main()
