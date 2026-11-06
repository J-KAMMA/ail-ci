"""tools/bench_history.py renders the fixed three-run sample to a stable page.

The sample lives in tools/testdata/bench_history/runs.jsonl and deliberately changes its task list
between the second and third run, so the chart must break the line there instead of joining the
points.  One task has a missing peak RSS in the first run, so a missing value stays missing rather
than becoming a number.
"""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SAMPLE = REPO / 'tools' / 'testdata' / 'bench_history' / 'runs.jsonl'
EXPECTED_SHA256 = 'cb2db918945eb08a028af1819997a5e710519919daba5b6b29a6f67f843ef28b'


def load_history():
    path = REPO / 'tools' / 'bench_history.py'
    spec = importlib.util.spec_from_file_location('bench_history', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BenchHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()
        cls.runs = cls.history.load_runs(SAMPLE)
        cls.text = cls.history.render_runs(cls.runs)

    def test_sample_render_has_the_fixed_hash(self):
        self.assertEqual(len(self.runs), 3)
        self.assertEqual(hashlib.sha256(self.text.encode('utf-8')).hexdigest(), EXPECTED_SHA256)

    def test_render_writes_exactly_the_rendered_text(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'index.html'
            returned = self.history.render(SAMPLE, output)
            self.assertEqual(output.read_text(encoding='utf-8'), returned)
            self.assertEqual(returned, self.text)

    def test_committed_page_is_a_fresh_render(self):
        runs = REPO / 'lab' / 'compare' / 'history' / 'runs.jsonl'
        page = REPO / 'lab' / 'compare' / 'history' / 'index.html'
        if not runs.is_file():
            self.skipTest('no committed history')
        self.assertEqual(page.read_text(encoding='utf-8'),
                         self.history.render_runs(self.history.load_runs(runs)))

    def test_page_is_self_contained(self):
        for needle in ('<script', 'src=', '@import', 'http://', 'https://'):
            self.assertNotIn(needle, self.text)
        self.assertEqual(self.text.count('<svg '), 6)

    def test_task_list_change_breaks_the_line(self):
        xs = list(range(len(self.runs)))
        values = [self.history.run_ratio(run, 'ail', 'wall_ms') for run in self.runs]
        signatures = [self.history.task_signature(run) for run in self.runs]
        segments = self.history.series_segments(xs, values, signatures)
        self.assertEqual([len(segment) for segment in segments], [2, 1])

    def test_missing_columns_are_marked_not_invented(self):
        report = {'head': 'abcdef0', 'date': '2026-11-06', 'tasks': [
            {'task': 'only', 'results': {'ail': {'wall_ms': 12.5, 'rss_kib': None}}}]}
        record = self.history.normalise_report(report, '1')
        values = record['tasks']['only']['ail']
        self.assertEqual(set(values), set(self.history.METRIC_KEYS))
        self.assertEqual(values['wall_ms'], 12.5)
        for key in ('rss_kib', 'binary_bytes', 'compile_s', 'build_disk_kib', 'instructions'):
            self.assertIsNone(values[key])
        self.assertEqual(record['commit'], 'abcdef0')
        self.assertEqual(record['date'], '2026-11-06')

    def test_sample_is_jsonl_and_keeps_the_six_columns(self):
        lines = SAMPLE.read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            record = json.loads(line)
            self.assertEqual(set(record), {'run', 'commit', 'date', 'tasks'})
            for task in record['tasks'].values():
                for language in task.values():
                    self.assertEqual(set(language), set(self.history.METRIC_KEYS))
