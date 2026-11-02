"""tools/compare_publish.py renders the committed fixture into docs/COMPARISON.md.

The fixture is tools/testdata/compare-report.json (run 41393616319, commit 4f1245b).  It carries
only the numbers supplied for that run and leaves the rest absent, so the generator has to show
not run/n-a rather than invent values.  The committed document must equal a fresh render: no number
in it is hand-edited.  Every metric column, both AIL columns, the geomean rows, the toolchain
versions, the refusals and the method section are checked.
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
FIXTURE = 'tools/testdata/compare-report.json'
DOC = REPO / 'docs' / 'COMPARISON.md'


def load_publisher():
    path = REPO / 'tools' / 'compare_publish.py'
    spec = importlib.util.spec_from_file_location('compare_publish', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComparePublish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.publisher = load_publisher()
        cls.report = cls.publisher.load_report(REPO / FIXTURE)
        cls.text = cls.publisher.render(cls.report, source=Path(FIXTURE).name, fixture=FIXTURE)

    def test_committed_document_is_a_fresh_render(self):
        self.assertEqual(DOC.read_text(encoding='utf-8'), self.text,
                         'docs/COMPARISON.md differs from the fixture render; run tools/compare_publish.py')

    def test_header_has_commit_date_run_and_fixture(self):
        for needle in ('`4f1245b`', 'date 2026-11-02', 'run 41393616319', 'fixture `%s`' % FIXTURE):
            self.assertIn(needle, self.text)

    def test_every_metric_column_and_geomean_row(self):
        for _key, title, _fmt in self.publisher.merge.METRICS:
            self.assertIn('### ' + title, self.text)
        self.assertEqual(self.text.count('**geomean**'), len(self.publisher.merge.METRICS))

    def test_scorecards_against_rust_and_best_other_for_both_ail_columns(self):
        for lang in ('AIL', 'AIL (py src)'):
            self.assertIn('### %s vs Rust' % lang, self.text)
            self.assertIn('### %s vs the best other language' % lang, self.text)

    def test_toolchain_versions_are_not_invented(self):
        self.assertIn('No tool versions in the report.', self.text)
        self.assertNotIn('rustc 1.99.1', self.text)

    def test_ail_py_table_includes_refusals(self):
        for task in ('scar_life', 'tally_lang', 'tree_fold'):
            self.assertIn('| %s | - | refused |' % task, self.text)
        self.assertIn("refused: import of 're' with a use that is not built", self.text)

    def test_ail_py_table_does_not_copy_the_ail_metrics(self):
        self.assertIn('| berth_sim | not run | n/a |', self.text)
        self.assertNotIn('| berth_sim | - | n/a | - | - | W', self.text)
        self.assertNotIn('why not typed:', self.text)

    def test_method_section_is_unchanged(self):
        for line in self.publisher.merge.METHOD_LINES:
            self.assertIn(line, self.text)

    def test_win_counts_against_rust(self):
        counts = self.publisher.summary_counts(self.report)
        expected = {
            'instructions': [0, 0], 'rss_kib': [0, 4], 'binary_bytes': [0, 0],
            'compile_s': [0, 0], 'build_disk_kib': [0, 0], 'wall_ms': [6, 10],
        }
        self.assertEqual(counts, expected)

    def test_supplied_ranges_give_the_binary_and_compile_counts(self):
        self.assertEqual(self.publisher.range_counts(self.report, 'binary_bytes'), [10, 10])
        self.assertEqual(self.publisher.range_counts(self.report, 'compile_s'), [0, 10])
        self.assertIn('Supplied range (no per-task values): AIL 34–102; Rust 4450–4518; AIL lower on 10/10 tasks.',
                      self.text)
        self.assertIn('Supplied range (no per-task values): AIL 1.87–11.17; Rust 0.19–0.56; AIL lower on 0/10 tasks.',
                      self.text)

    def test_fixture_carries_only_supplied_metrics(self):
        for task in self.report['tasks']:
            self.assertLessEqual(set(task['results']), {'ail', 'ail-py', 'rust'})
            for result in task['results'].values():
                for key in ('instructions', 'build_disk_kib', 'cases_public', 'cases_hidden',
                            'binary_bytes', 'compile_s'):
                    self.assertNotIn(key, result)
            self.assertNotIn('path', task['results']['ail'])
            self.assertNotIn('why_not_typed', task['results']['ail'])
            if 'ail-py' in task['results']:
                self.assertEqual(task['results']['ail-py']['path'], 'refused')
        self.assertEqual(set(self.report['ranges']), {'binary_bytes', 'compile_s'})
        for task in self.report['tasks']:
            self.assertNotIn('tools', task)
            self.assertNotIn('pins', task)

    def test_date_survives_the_merge_report_shape(self):
        with tempfile.TemporaryDirectory(prefix='compare-merge-') as tmp:
            results = Path(tmp) / 'results'
            results.mkdir()
            for number, task in enumerate(self.report['tasks']):
                (results / ('result-%02d.json' % number)).write_text(json.dumps(task), encoding='utf-8')
            merged_path = Path(tmp) / 'compare-report.json'
            subprocess.run([sys.executable, str(REPO / 'lab' / 'compare' / 'merge.py'),
                            str(results), '--json', str(merged_path)],
                           check=True, capture_output=True)
            merged = json.loads(merged_path.read_text(encoding='utf-8'))
            text = self.publisher.render(merged, source='compare-report.json')
            self.assertIn('AIL commit `4f1245b`', text)
            self.assertIn('date 2026-11-02', text)

    def test_readme_counts_match_the_fixture(self):
        counts = self.publisher.summary_counts(self.report)
        binary = self.publisher.range_counts(self.report, 'binary_bytes')
        compile_counts = self.publisher.range_counts(self.report, 'compile_s')
        readme = (REPO / 'README.md').read_text(encoding='utf-8')
        self.assertIn('Peak RSS: AIL is lower on %d/%d tasks with data.' % tuple(counts['rss_kib']), readme)
        self.assertIn('Binary size: AIL is smaller on %d/%d tasks.' % tuple(binary), readme)
        compile_slower = compile_counts[1] - compile_counts[0]
        self.assertIn('Compile time: AIL is slower to compile on %d/%d tasks.' % (compile_slower, compile_counts[1]), readme)
        self.assertIn('Wall time: AIL is lower on %d/%d tasks.' % tuple(counts['wall_ms']), readme)
        self.assertNotIn('against C, Rust, Go, Nim and Python', readme)

    def test_main_writes_the_same_document(self):
        with tempfile.TemporaryDirectory(prefix='compare-publish-') as tmp:
            out = Path(tmp) / 'COMPARISON.md'
            code = self.publisher.main([str(REPO / FIXTURE), '-o', str(out), '--fixture', FIXTURE])
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding='utf-8'), self.text)


if __name__ == '__main__':
    unittest.main()
