"""tools/compare_publish.py renders the committed fixture into docs/COMPARISON.md.

The fixture is tools/testdata/compare-report.json (run 41393616319, commit 4f1245b).  The committed
document must equal a fresh render: no number in it is hand-edited.  Every metric column, both AIL
columns, the geomean rows, the toolchain versions, the refusals and the method section are checked.
"""
import importlib.util
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

    def test_toolchain_versions(self):
        self.assertIn('gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0', self.text)
        self.assertIn('rustc 1.99.1 (58cf8f9c3 2026-10-13)', self.text)

    def test_ail_py_table_includes_refusals(self):
        self.assertIn('| chain_relax | general | refused |', self.text)
        self.assertIn('| rail_transfer | general | refused |', self.text)
        self.assertIn('refused: a call can raise or have side effects', self.text)

    def test_method_section_is_unchanged(self):
        for line in self.publisher.merge.METHOD_LINES:
            self.assertIn(line, self.text)

    def test_win_counts_against_rust(self):
        counts = self.publisher.summary_counts(self.report)
        expected = {
            'instructions': [5, 10], 'rss_kib': [6, 10], 'binary_bytes': [10, 10],
            'compile_s': [0, 10], 'build_disk_kib': [2, 10], 'wall_ms': [6, 10],
        }
        self.assertEqual(counts, expected)

    def test_main_writes_the_same_document(self):
        with tempfile.TemporaryDirectory(prefix='compare-publish-') as tmp:
            out = Path(tmp) / 'COMPARISON.md'
            code = self.publisher.main([str(REPO / FIXTURE), '-o', str(out), '--fixture', FIXTURE])
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding='utf-8'), self.text)


if __name__ == '__main__':
    unittest.main()
