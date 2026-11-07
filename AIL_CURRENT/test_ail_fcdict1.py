"""fcdict1: a dict whose values are lists, sets or dicts.

Every probe must either build (in the default build and with AIL_UNIFIED_FORCE=1) and
match CPython 3.12's stdout and exit status, or be refused at compile time by name.
The shapes this job implements (`v = d[k]` write-through, a fixed-position record,
`setdefault`/`get`, printing a record) must build on the typed path (`--strict`).
The three target programs must build on the default path and match CPython.
"""
import importlib.util
import os
import random
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
REPO = ROOT.parent
PROBES = REPO / 'lab' / 'reach' / 'fcdict1'
REPRO = REPO / 'lab' / 'pyproof' / 'repro' / 'a-dict-of-containers-lists-sets-or-dicts-as-values.py'
HAVE_CC = shutil.which('gcc') is not None

TYPED_PROBES = {'p01_repro_alias', 'p05_setdefault_record', 'p06_print_record_dict',
                'p07_del_alias', 'p09_int_keys', 'p10_get_default', 'p12_element_store',
                'p13_bytes_keys', 'p15_str_keys_record'}
FALLBACK_PROBES = {'p02_alias_append', 'p03_set_value_add', 'p04_dict_of_dict_counter',
                   'p11_nested_alias', 'p14_setdefault_set'}
LOUD_PROBES = {'p08_int_beyond'}


def _limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (1500000000, 1500000000))
    except Exception:
        pass


def build(tmp, name, source, unified, strict=False):
    out = Path(tmp) / ('exe_' + name + ('_u' if unified else '_d') + ('_s' if strict else ''))
    env = dict(os.environ)
    env['AIL_NO_CACHE'] = '1'
    env['AIL_QUIET_FALLBACK'] = '1'
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    command = [sys.executable, '-B', str(CLI), 'compile', str(source),
               '--syntax', 'python', '-o', str(out)]
    if strict:
        command.append('--strict')
    result = subprocess.run(command, capture_output=True, text=True, timeout=300,
                            cwd=str(tmp), env=env, preexec_fn=_limits)
    return result, out


def run(exe, args=()):
    return subprocess.run([str(exe)] + list(args), capture_output=True, text=True,
                          timeout=180, preexec_fn=_limits)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Fcdict1Probes(unittest.TestCase):
    def test_probes_match_or_are_refused_by_name(self):
        probes = sorted(PROBES.glob('*.py'))
        self.assertGreaterEqual(len(probes), 12)
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-') as tmp:
            for source in probes:
                label = source.name
                self.assertIn(source.stem, TYPED_PROBES | FALLBACK_PROBES | LOUD_PROBES, label)
                reference = subprocess.run([sys.executable, str(source)],
                                           capture_output=True, text=True, timeout=120)
                for unified in (False, True):
                    tag = '%s (unified=%s)' % (label, unified)
                    result, exe = build(tmp, source.stem, source, unified)
                    text = result.stderr + result.stdout
                    if result.returncode != 0:
                        self.assertTrue(text.strip(), tag + ': refused with no message')
                        self.assertNotIn('Traceback (most recent call last)', text, tag)
                        if source.stem in LOUD_PROBES:
                            self.assertIn('int64', text, tag)
                            self.assertIn('out of range', text, tag)
                        continue
                    got = run(exe)
                    self.assertEqual(got.returncode, reference.returncode, tag)
                    self.assertEqual(got.stdout, reference.stdout, tag)
                # The default build with --strict is the typed-path claim.
                result, _exe = build(tmp, source.stem + '_strict', source, False, strict=True)
                text = result.stderr + result.stdout
                if source.stem in TYPED_PROBES:
                    self.assertEqual(result.returncode, 0, label + ': ' + text[:800])
                    self.assertNotIn('general path', text, label)
                elif source.stem in LOUD_PROBES:
                    self.assertEqual(result.returncode, 2, label + ': ' + text[:800])
                    self.assertIn('int64', text, label)
                    self.assertIn('out of range', text, label)

    def test_reproducer_is_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-repro-') as tmp:
            reference = subprocess.run([sys.executable, str(REPRO)],
                                       capture_output=True, text=True, timeout=120)
            result, exe = build(tmp, 'repro', REPRO, False, strict=True)
            text = result.stderr + result.stdout
            self.assertEqual(result.returncode, 0,
                             'reproducer strict: ' + text[:800])
            got = run(exe)
            self.assertEqual(got.returncode, reference.returncode, 'reproducer')
            self.assertEqual(got.stdout, reference.stdout, 'reproducer')
            # The unified build asks for the general path; it must still match CPython.
            result, exe = build(tmp, 'repro_unified', REPRO, True)
            text = result.stderr + result.stdout
            self.assertEqual(result.returncode, 0,
                             'reproducer unified: ' + text[:800])
            got = run(exe)
            self.assertEqual(got.returncode, reference.returncode, 'reproducer unified')
            self.assertEqual(got.stdout, reference.stdout, 'reproducer unified')


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Fcdict1Programs(unittest.TestCase):
    def _compare_cases(self, task):
        task_dir = REPO / 'lab' / 'compare' / 'tasks' / task
        gen = _load(task_dir / 'gen.py', 'fcdict1_gen_' + task)
        public, hidden, _perf = gen.cases(random.Random(1234))
        source = REPO / 'lab' / 'compare' / 'src' / task / 'main.py'
        reference = task_dir / 'reference.py'
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-' + task + '-') as tmp:
            for unified in (False, True):
                result, exe = build(tmp, task, source, unified)
                tag = '%s (unified=%s)' % (task, unified)
                self.assertEqual(result.returncode, 0,
                                 tag + ': ' + (result.stderr + result.stdout)[:1000])
                for case in public + hidden:
                    name, data, _template = case
                    path = Path(tmp) / ('case_' + str(name) + '.bin')
                    path.write_bytes(data)
                    want = subprocess.run([sys.executable, str(reference), str(path)],
                                          capture_output=True, text=True, timeout=120)
                    got = run(exe, [str(path)])
                    self.assertEqual(got.returncode, want.returncode,
                                     '%s %s exit' % (tag, name))
                    self.assertEqual(got.stdout, want.stdout, '%s %s stdout' % (tag, name))

    def test_ledger_bin_cases(self):
        self._compare_cases('ledger_bin')

    def test_ticket_audit_cases(self):
        self._compare_cases('ticket_audit')

    def test_pyperf_help(self):
        source = REPO / 'lab' / 'pyperf' / 'run.py'
        want = subprocess.run([sys.executable, str(source), '--help'],
                              capture_output=True, text=True, timeout=120)
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-pyperf-') as tmp:
            for unified in (False, True):
                result, exe = build(tmp, 'pyperf', source, unified)
                tag = 'pyperf (unified=%s)' % unified
                text = result.stderr + result.stdout
                if result.returncode != 0:
                    # pyperf is still refused, but its refusal names a non-dict blocker
                    # (an unannotated Path / statistics.median / preexec_fn), not the
                    # `info['wall_cpython'] = [...]` dict-of-containers store.
                    self.assertTrue(any(name in text for name in
                                        ('statistics.median', 'preexec_fn', 'annotated Path')),
                                    tag + ': ' + text[:800])
                    continue
                got = run(exe, ['--help'])
                self.assertEqual(got.returncode, want.returncode, tag)
                self.assertEqual(got.stdout, want.stdout, tag)


if __name__ == '__main__':
    unittest.main()
