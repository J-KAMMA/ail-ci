"""fcdict1: probes for a dict whose values are lists, sets or dicts.

Every probe must either build (in the default build and with AIL_UNIFIED_FORCE=1) and
match CPython 3.12's stdout and exit status, or be refused at compile time by name.
That property is what the eventual typed-path support has to keep; it also lets this
module cover the shapes the current source-level dict-of-records pass still leaves on
the general path.
"""
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
PROBES = Path(__file__).resolve().parent.parent / 'lab' / 'reach' / 'fcdict1'
HAVE_CC = shutil.which('gcc') is not None


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (1500000000, 1500000000))
    except Exception:
        pass


def build(tmp, name, source, unified):
    out = Path(tmp) / ('exe_' + name + ('_u' if unified else '_d'))
    env = dict(os.environ)
    env['AIL_NO_CACHE'] = '1'
    env['AIL_QUIET_FALLBACK'] = '1'
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(out)],
                            capture_output=True, text=True, timeout=180,
                            cwd=str(tmp), env=env, preexec_fn=_limits)
    return result, out


def run(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          preexec_fn=_limits)


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Fcdict1Probes(unittest.TestCase):
    def test_probes_match_or_are_refused_by_name(self):
        probes = sorted(PROBES.glob('*.py'))
        self.assertGreaterEqual(len(probes), 12)
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-') as tmp:
            for source in probes:
                reference = subprocess.run([sys.executable, str(source)],
                                           capture_output=True, text=True, timeout=120)
                for unified in (False, True):
                    result, exe = build(tmp, source.stem, source, unified)
                    label = '%s (unified=%s)' % (source.name, unified)
                    if result.returncode != 0:
                        text = result.stderr + result.stdout
                        self.assertTrue(text.strip(), label + ': refused with no message')
                        self.assertNotIn('Traceback (most recent call last)', text, label)
                        continue
                    got = run(exe)
                    self.assertEqual(got.returncode, reference.returncode, label)
                    self.assertEqual(got.stdout, reference.stdout, label)


if __name__ == '__main__':
    unittest.main()
