"""Stub-typed stdlib calls on the general path (typeshed2): the five probes in lab/typeshed.

C1  probe_gcd/probe_shadow/probe_types match CPython 3.12 in the default build and with
    AIL_UNIFIED_FORCE=1; probe_big/probe_text stop with the same integer-overflow error in both builds
    (AIL ints are int64 on this path, as they were before this change), with no stdout
C2  probe_gcd's generated C carries the stub marker for math.gcd and the checked unbox of math.isqrt
    / math.sqrt; AIL_STUBCALLS=0 removes every marker
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
PROBES = REPO / 'lab' / 'typeshed'
ON_312 = sys.version_info[:2] == (3, 12)
HAVE_CC = shutil.which(os.environ.get('CC', 'cc')) is not None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding='utf-8')
    return r.returncode, r.stdout, r.stderr


def build(directory, source, mode, extra=None):
    exe = Path(directory, source.stem + '-' + mode)
    env = dict(os.environ)
    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_STUBCALLS'):
        env.pop(k, None)
    env['AIL_SERVER'] = '0'
    env['AIL_SERVER_DIR'] = tempfile.mkdtemp(dir=directory)
    env['AIL_NO_CACHE'] = '1'
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    if extra:
        env.update(extra)
    dbg = Path(tempfile.mkdtemp(dir=directory, prefix='dbg-'))
    dbg.rmdir()
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                        '--syntax', 'python', '-o', str(exe), '--debug-dir', str(dbg)],
                       cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return r, exe, dbg / 'program.c'


@unittest.skipUnless(ON_312, 'the oracle is CPython 3.12')
@unittest.skipUnless(HAVE_CC, 'no C compiler')
class StubCalls(unittest.TestCase):
    def test_probes_match_cpython(self):
        for name in ('probe_gcd.py', 'probe_shadow.py', 'probe_types.py'):
            source = PROBES / name
            want = run([sys.executable, str(source)])
            with tempfile.TemporaryDirectory() as d:
                for mode in ('default', 'general'):
                    r, exe, _ = build(d, source, mode)
                    self.assertEqual(r.returncode, 0, '%s %s: %s' % (name, mode, r.stderr[-800:]))
                    got = run([str(exe)])
                    self.assertEqual(got, want, '%s %s' % (name, mode))

    def test_big_and_text_stop_as_before(self):
        for name in ('probe_big.py', 'probe_text.py'):
            source = PROBES / name
            seen = []
            with tempfile.TemporaryDirectory() as d:
                for mode in ('default', 'general'):
                    r, exe, _ = build(d, source, mode)
                    self.assertEqual(r.returncode, 0, '%s %s: %s' % (name, mode, r.stderr[-800:]))
                    rc, out, err = run([str(exe)])
                    self.assertEqual(rc, 1, '%s %s' % (name, mode))
                    self.assertEqual(out, '', '%s %s printed a value' % (name, mode))
                    self.assertIn('integer overflow', err, '%s %s' % (name, mode))
                    seen.append((rc, out, err))
            self.assertEqual(seen[0], seen[1], name)

    def test_markers(self):
        source = PROBES / 'probe_gcd.py'
        with tempfile.TemporaryDirectory() as d:
            r, _, cpath = build(d, source, 'general')
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            c = cpath.read_text(encoding='utf-8')
            self.assertIn('AIL stub call math.gcd: typed clone', c)
            self.assertIn('AIL stub call math.isqrt: stub says int', c)
            self.assertIn('AIL stub call math.sqrt: stub says float', c)
            r, _, cpath = build(d, source, 'off', {'AIL_STUBCALLS': '0'})
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            off = cpath.read_text(encoding='utf-8')
            self.assertNotIn('AIL stub call', off)


if __name__ == '__main__':
    unittest.main()
