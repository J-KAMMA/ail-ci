"""Python-syntax reach, fcdict1: a dict of containers near the typed path.

What this module pins down:

P1  the task's reproducer
    (`lab/pyproof/repro/a-dict-of-containers-lists-sets-or-dicts-as-values.py`) builds on
    the typed path and prints CPython's list text: `v = d[k]` aliases the stored row, so
    `v[0] = v[1]` changes `d[k]` too;
P2  probes p07, p10 and p11 (a record row printed whole) build typed and match CPython in the
    default and the `AIL_UNIFIED_FORCE=1` build; p07's row mixes str, int and bool and is
    printed through CPython's `repr` of each field;
P3  the shapes the record lowering does not model -- a growing value list, a set value, a
    dict-of-dict, a record printed together with the whole dict, a variable index over mixed
    kinds -- stay on the general path in the default build (matching CPython) and are refused
    **by name** under `--strict`, never by a crash or a downstream symptom alone;
P4  p08 exercises the int64 boundary at runtime: the default build stops loudly with
    `OverflowError` for a value beyond int64, and `--exact-int` refuses the shape by name;
P5  ledger_bin and ticket_audit keep their recorded classification (general; the recorded
    first `--strict` blocker) and their default build matches the task's CPython reference
    on every public case;
P6  `lab/pyperf/run.py` keeps its recorded classification (refused, and not for a dict
    reason alone).
"""
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / 'ail_chatgpt.py'
PROBES = REPO / 'lab' / 'reach' / 'fcdict1'
REPRO = REPO / 'lab' / 'pyproof' / 'repro' / 'a-dict-of-containers-lists-sets-or-dicts-as-values.py'
COMPARE = REPO / 'lab' / 'compare'
HAVE_CC = shutil.which('gcc') is not None

TYPED_PROBES = ('p01_repro', 'p05_setdefault_record', 'p07_del_alias', 'p10_alias_write',
                'p11_get_default')
REFUSED_PROBES = ('p02_alias_append', 'p03_set_add', 'p04_dictdict_counter', 'p06_print_record',
                  'p09_record_grow', 'p12_set_store', 'p13_dict_store',
                  'p14_var_index_record')
DICT_NAME = 'dict of containers'


def build(work, name, source, strict=False, extra=(), timeout=420):
    exe = work / name
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if strict:
        env['AIL_NO_GENERAL'] = '1'
    else:
        env.pop('AIL_NO_GENERAL', None)
    cmd = [sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
           *extra, '-o', str(exe)]
    if strict:
        cmd.insert(5, '--strict')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return result, exe


def build_unified(work, name, source, timeout=420):
    exe = work / (name + '_unified')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_UNIFIED_FORCE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(exe)],
                            capture_output=True, text=True, timeout=timeout, env=env)
    return result, exe


def run(exe, *args, timeout=120):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=timeout)


def cp(source, *args):
    return subprocess.run([sys.executable, '-B', str(source), *args], capture_output=True,
                          text=True, timeout=120)


def load_cases(task):
    spec = importlib.util.spec_from_file_location(
        'fcdict1_' + task, str(COMPARE / 'tasks' / task / 'gen.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public, _hidden, _perf = module.cases(random.Random('%s-20261012' % task))
    return public


def check_task_cases(test, task):
    """Build the task's CPython source with the default command and run every public case
    beside the task's CPython `reference.py`."""
    source = COMPARE / 'src' / task / 'main.py'
    reference = COMPARE / 'tasks' / task / 'reference.py'
    with tempfile.TemporaryDirectory(prefix='ail-fcdict1-%s-' % task) as tmp:
        work = Path(tmp)
        result, exe = build(work, task, source, timeout=420)
        test.assertEqual(result.returncode, 0, (task, result.stdout[-2000:], result.stderr[-3000:]))
        for name, data, _args in load_cases(task):
            case = work / ('%s.bin' % name)
            case.write_bytes(data)
            expected = subprocess.run([sys.executable, '-B', str(reference), str(case)],
                                      capture_output=True, timeout=120)
            got = run(exe, str(case))
            test.assertEqual((got.returncode, got.stdout),
                             (expected.returncode, expected.stdout.decode('utf8', 'replace')),
                             (task, name))


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fcdict1(unittest.TestCase):
    def test_reproducer_is_typed_and_aliases_the_row(self):
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-repro-') as tmp:
            work = Path(tmp)
            expected = cp(REPRO)
            self.assertEqual(expected.returncode, 0)
            for unified in (False, True):
                if unified:
                    result, exe = build_unified(work, 'repro', REPRO)
                else:
                    result, exe = build(work, 'repro', REPRO, strict=True)
                self.assertEqual(result.returncode, 0, (unified, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual((got.returncode, got.stdout),
                                 (expected.returncode, expected.stdout), unified)

    def test_all_int_row_prints_are_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-typed-') as tmp:
            work = Path(tmp)
            for name in TYPED_PROBES:
                source = PROBES / (name + '.py')
                expected = cp(source)
                self.assertEqual(expected.returncode, 0, name)
                for strict in (True, False):
                    result, exe = build(work, name + ('_s' if strict else '_d'), source,
                                        strict=strict, timeout=240)
                    self.assertEqual(result.returncode, 0, (name, strict, result.stderr[-3000:]))
                    got = run(exe)
                    self.assertEqual((got.returncode, got.stdout),
                                     (expected.returncode, expected.stdout), (name, strict))
                result, exe = build_unified(work, name, source, timeout=240)
                self.assertEqual(result.returncode, 0, (name, 'unified', result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual((got.returncode, got.stdout),
                                 (expected.returncode, expected.stdout), (name, 'unified'))

    def test_unmodelled_shapes_match_cpython_and_refuse_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-refused-') as tmp:
            work = Path(tmp)
            for name in REFUSED_PROBES:
                source = PROBES / (name + '.py')
                expected = cp(source)
                self.assertEqual(expected.returncode, 0, name)
                result, exe = build(work, name + '_d', source, timeout=240)
                self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
                got = run(exe)
                self.assertEqual((got.returncode, got.stdout),
                                 (expected.returncode, expected.stdout), name)
                refused, _ = build(work, name + '_s', source, strict=True, timeout=240)
                self.assertNotEqual(refused.returncode, 0, name)
                self.assertIn(DICT_NAME, refused.stdout + refused.stderr, name)

    def test_int64_boundary_stops_loudly_or_refuses_by_name(self):
        source = PROBES / 'p08_int64_record.py'
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-int64-') as tmp:
            work = Path(tmp)
            result, exe = build(work, 'p08', source, strict=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            got = run(exe)
            self.assertNotEqual(got.returncode, 0)
            self.assertIn('OverflowError', got.stderr)
            got = run(exe, '9223372036854775808123')
            self.assertNotEqual(got.returncode, 0)
            self.assertIn('OverflowError', got.stderr)
            refused, _ = build(work, 'p08_exact', source, strict=True,
                               extra=('--exact-int',), timeout=240)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(DICT_NAME, refused.stdout + refused.stderr)

    def test_ledger_bin_keeps_its_recorded_classification_and_cases(self):
        check_task_cases(self, 'ledger_bin')
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-ledger-') as tmp:
            result, _ = build(Path(tmp), 'ledger_strict',
                              COMPARE / 'src' / 'ledger_bin' / 'main.py',
                              strict=True, timeout=300)
            self.assertNotEqual(result.returncode, 0)
            text = result.stdout + result.stderr
            self.assertIn('nested def inside a loop', text)

    def test_ticket_audit_keeps_its_recorded_classification_and_cases(self):
        check_task_cases(self, 'ticket_audit')
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-ticket-') as tmp:
            result, _ = build(Path(tmp), 'ticket_strict',
                              COMPARE / 'src' / 'ticket_audit' / 'main.py',
                              strict=True, timeout=600)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(DICT_NAME, result.stdout + result.stderr)

    def test_pyperf_run_stays_refused(self):
        source = REPO / 'lab' / 'pyperf' / 'run.py'
        with tempfile.TemporaryDirectory(prefix='ail-fcdict1-pyperf-') as tmp:
            result, exe = build(Path(tmp), 'runpy', source, timeout=300)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('statistics.median', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
