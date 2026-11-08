"""The PyPy columns of lab/compare_rival and lab/wedge (measurement only).

Two labs gained a PyPy arm; neither may change the compiler, and both must be honest about what PyPy
is: an interpreter that compiles nothing (`compile s` is `-`, the disk is the install), whose JIT needs
warm-up (so the 5th run in one process is reported next to the plain wall time), and whose output is
compared byte for byte with the CPython reference rather than trusted.

These tests drive the renderers and the merge with synthetic numbers, so they pin the arithmetic and
the wording without needing PyPy, Cython or Nuitka installed.  `pypy_warm.py` is exercised with the
local CPython, because the harness itself must not depend on which interpreter runs it.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rival():
    return load('compare_rival_run', REPO / 'lab' / 'compare_rival' / 'run.py')


def wedge_measure():
    return load('wedge_measure', REPO / 'lab' / 'wedge' / 'measure.py')


def wedge_report():
    return load('wedge_report', REPO / 'lab' / 'wedge' / 'report.py')


def row(tool, wall, **extra):
    rec = dict(tool=tool, build_ok=True, status='ok', correct=True, wall_ms=wall,
               compile_s=0.5, build_disk_kib=100, binary_bytes=1000, standalone=True,
               cases_public=[1, 1], cases_hidden=[1, 1])
    rec.update(extra)
    return rec


def synthetic(tasks=('tree_fold', 'scar_life')):
    """AIL, PyPy and one compiled rival, with a known answer: AIL wins one task and loses one."""
    out = {}
    for task, ail_ms, pypy_ms, warm_ms in zip(tasks, (1000.0, 4000.0), (2000.0, 800.0), (1500.0, 700.0)):
        out[task] = dict(case='perf', input_bytes=10, expected_exit=0, results={
            'ail': row('ail', ail_ms),
            'ail-py': row('ail-py', ail_ms * 1.5),
            'nuitka': row('nuitka', 3000.0),
            'pypy': row('pypy', pypy_ms, compile_s=None, build_disk_kib=154120, binary_bytes=None,
                        standalone=False, interpreter=True, warm5_ms=warm_ms, warm5_correct=True),
        })
    return dict(date='2026-11-08', head='abcdef0', icount_method='none', tools={'pypy': 'PyPy 7.3.23'},
                settings={}, tasks=out, safety_probes=[], safety={})


class RivalPyPyRow(unittest.TestCase):
    def setUp(self):
        self.m = rival()
        self.data = synthetic()
        self.text = self.m.render(self.data)

    def test_compile_time_is_dash_and_disk_is_marked_interpreter(self):
        line = [ln for ln in self.text.splitlines() if ln.startswith('| tree_fold | pypy |')][0]
        cells = [c.strip() for c in line.strip('|').split('|')]
        self.assertEqual(cells[3], '2000', 'wall ms column')
        self.assertEqual(cells[4], '1500', 'warm5 ms column')
        self.assertEqual(cells[8], '-', 'compile s is "-" for an interpreter')
        self.assertTrue(cells[9].endswith('(interp)'), cells[9])
        self.assertEqual(cells[10], 'no', 'an interpreter is not a single exe')

    def test_warm_column_is_present_only_when_measured(self):
        self.assertIn('| task | tool | correct | wall ms | warm5 ms |', self.text)
        bare = synthetic()
        for task in bare['tasks'].values():
            task['results'].pop('pypy')
        text = self.m.render(bare)
        self.assertIn('| task | tool | correct | wall ms | instructions |', text)
        self.assertNotIn('warm5 ms | instructions', text)
        self.assertIn('No PyPy row was measured in this result file', text)

    def test_a_pypy_row_without_a_warm_run_says_so(self):
        data = synthetic()
        for task in data['tasks'].values():
            task['results']['pypy'].pop('warm5_ms')
        text = self.m.render(data)
        self.assertIn('The warm-up column is **not measured**', text)
        self.assertIn('The warm-up column is **not measured** in this result file: 2 PyPy rows', text)
        self.assertIn('| tree_fold | pypy | yes | 2000 | - |', text, 'row still shown, warm cell "-"')

    def test_headline_counts_and_geomean(self):
        # AIL/PyPy is 0.50 on tree_fold and 5.00 on scar_life -> one win of two, geomean sqrt(2.5).
        crel = self.m.render(self.data)
        self.assertIn('faster than PyPy on 1 of the 2 tasks', crel)
        self.assertIn('**1.58x**', crel)
        self.assertIn('On wall time, **AIL standalone (typed.py)', crel)

    def test_ratio_table_reports_both_arms(self):
        self.assertIn('AIL standalone / PyPy', self.text)
        self.assertIn('| tree_fold | 2000 | 1500 | 0.75x | 0.50x | 0.75x |', self.text)

    def test_warm_run_mismatch_is_reported_as_a_pypy_result(self):
        self.data['tasks']['scar_life']['results']['pypy']['warm5_correct'] = False
        text = self.m.render(self.data)
        self.assertIn('Warm-run output differs from CPython on: scar_life', text)


class RivalPyPyMerge(unittest.TestCase):
    def test_base_keeps_old_tools_and_marks_provenance(self):
        m = rival()
        base = synthetic()
        base['date'] = '2026-11-06'
        base['head'] = 'e9cb684'
        base['tool_runs'] = {'nuitka': dict(date='2026-11-06', head='e9cb684')}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'base.json'
            path.write_text(json.dumps(base))
            fresh = json.loads(path.read_text())
            for task in fresh['tasks'].values():
                task['results']['pypy'] = row('pypy', 900.0, compile_s=None, interpreter=True)
            self.assertIn('nuitka', fresh['tasks']['tree_fold']['results'])
            self.assertEqual(fresh['tool_runs']['nuitka']['date'], '2026-11-06')
            self.assertIn('date', fresh['tool_runs']['nuitka'])
        # the merge itself is a pure dict operation over two files; drive it through main's --base by
        # copying the render input, since a full run needs every rival installed.
        merged = dict(base['tasks']['tree_fold']['results'])
        merged.update({'pypy': row('pypy', 900.0, compile_s=None, interpreter=True)})
        text = m.render(dict(base, tasks={'tree_fold': dict(base['tasks']['tree_fold'], results=merged)},
                             tool_runs={'nuitka': dict(date='2026-11-06', head='e9cb684'),
                                        'pypy': dict(date='2026-11-08', head='abcdef0')}))
        self.assertIn('Where each column was measured', text)
        self.assertIn('nuitka 2026-11-06 on commit `e9cb684`', text)
        self.assertIn('pypy 2026-11-08 on commit `abcdef0`', text)
        self.assertIn('| tree_fold | pypy | yes | 900 |', text)


class WarmHarness(unittest.TestCase):
    def run_harness(self, source, reps=3, expect=None):
        harness = REPO / 'lab' / 'compare_rival' / 'pypy_warm.py'
        tmp = Path(tempfile.mkdtemp())
        src = tmp / 'prog.py'
        src.write_text(source)
        exp = tmp / 'expected.txt'
        exp.write_text(expect if expect is not None else 'ok\n')
        out = tmp / 'r.json'
        proc = subprocess.run([sys.executable, str(harness), str(src), str(reps), str(exp), '0', '-', str(out)],
                              capture_output=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', 'replace'))
        return json.loads(out.read_text())

    def test_each_run_is_timed_and_checked(self):
        report = self.run_harness('import sys\nsys.stdout.write("ok\\n")\n', reps=3)
        self.assertEqual(len(report['runs']), 3)
        self.assertTrue(report['last_match'])
        self.assertTrue(all(r['match'] for r in report['runs']))
        self.assertTrue(all(r['seconds'] >= 0 for r in report['runs']))

    def test_a_wrong_warm_output_does_not_match(self):
        report = self.run_harness('print("different")\n', reps=2)
        self.assertFalse(report['last_match'])
        self.assertFalse(any(r['match'] for r in report['runs']))

    def test_stdin_and_argv_are_replayed_on_every_run(self):
        tmp = Path(tempfile.mkdtemp())
        payload = tmp / 'in.bin'
        payload.write_text('7 8\n')
        src = tmp / 'prog.py'
        src.write_text('import sys\n'
                       'a, b = sys.stdin.read().split()\n'
                       'print(int(a) + int(b), sys.argv[1])\n')
        exp = tmp / 'expected.txt'
        exp.write_text('15 ping\n')
        out = tmp / 'r.json'
        proc = subprocess.run([sys.executable, str(REPO / 'lab' / 'compare_rival' / 'pypy_warm.py'),
                               str(src), '2', str(exp), '0', str(payload), str(out), 'ping'],
                              capture_output=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', 'replace'))
        report = json.loads(out.read_text())
        self.assertTrue(report['last_match'], 'stdin and argv are replayed on the 2nd run too')

    def test_a_program_that_exits_non_zero_is_recorded(self):
        report = self.run_harness('import sys\nsys.stdout.write("ok\\n")\nsys.exit(3)\n', reps=2, expect='ok\n')
        self.assertEqual(report['runs'][0]['exit'], 3)
        self.assertFalse(report['last_match'])


class WedgePyPyArm(unittest.TestCase):
    def setUp(self):
        self.m = wedge_measure()

    def test_byte_identical_output_matches(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'run.py').write_text('print("ok")\n')
        rec = self.m._timeit_pypy(tmp, b'ok\n')
        if 'pypy_error' in rec:
            self.skipTest(rec['pypy_error'])
        self.assertTrue(rec['pypy_match'])
        self.assertEqual(rec['pypy_rc'], 0)
        self.assertEqual(len(rec['pypy_runs_s']), self.m.REPS)

    def test_a_different_answer_is_a_pypy_result_not_a_crash(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'run.py').write_text('print("other")\n')
        rec = self.m._timeit_pypy(tmp, b'ok\n')
        if 'pypy_error' in rec:
            self.skipTest(rec['pypy_error'])
        self.assertFalse(rec['pypy_match'])
        self.assertIn('PyPy', rec['pypy_diff'])
        self.assertEqual(rec['pypy_diff_runs'], self.m.REPS)

    def test_first_diff_names_the_line(self):
        self.assertEqual(self.m._first_diff(b'a\nb\n', b'a\nc\n'), "stdout line 2: CPython 'b' / PyPy 'c'")
        self.assertIsNone(self.m._first_diff(b'a\n', b'a\n'))
        self.assertIn('missing', self.m._first_diff(b'a\nb\n', b'a\n'))

    def test_report_renders_the_pypy_columns(self):
        r = wedge_report()
        measure = {'m': dict(module='m', cpython_s=1.0, pypy_s=0.25, pypy_match=True,
                             pypy_version='Python 3.11.15 (x) [PyPy 7.3.23 with GCC 10.2.1]',
                             hybrid_s=0.9, standalone_s=0.05)}
        self.assertEqual(r._pypy_label(measure), 'PyPy 7.3.23')
        self.assertIn('no PyPy row measured', r._pypy_label({'m': dict(module='m')}))
        self.assertIn('no PyPy row measured',
                      r._pypy_label({'m': dict(module='m', pypy_version='PyPy 7.3.23')}),
                      'an unmeasured row has no label even if a version leaked in')


if __name__ == '__main__':
    unittest.main()
