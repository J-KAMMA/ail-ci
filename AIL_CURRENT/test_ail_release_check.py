"""The release preflight drives a fixture repository: versions, P0 merges, DIFFERENCES rows, exit and JSON."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools' / 'release_check.py'

ROADMAP = '''# Roadmap

## P0 - Release blockers

| Job | What it delivers |
| --- | --- |
| alpha | The first condition. |
| beta | The second condition. |

**Done when:** all jobs are merged.

## P1 - Python proof

- **Done when:** the `.py` sources reach the typed path on 10/10 tasks and land within 1.5x of the `.ail` sources.

## P3 - Release 0.1

1. Merge `integ` into `main`.
'''

DIFFERENCES = '''# Differences

| id | area | difference | status |
| --- | --- | --- | --- |
| X-1 | area one | first open row | open |
| X-2 | area two | second open row | open |
| X-3 | area three | a fixed row | fixed |
'''


class ReleaseCheckFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-release-check-test-')
        self.repo = Path(self.temporary.name)
        self.git('init', '-q')
        self.git('checkout', '-q', '-b', 'main')
        self.git('config', 'user.email', 'agent@example.com')
        self.git('config', 'user.name', 'AIL agent')
        self.write('packaging/ail_lang/__init__.py', '__version__ = "0.1.0.dev0"\n')
        self.write('pyproject.toml', '[project]\nname = "ailc"\nlicense = "MIT OR Apache-2.0"\n')
        self.write('CHANGELOG.md', '# Changelog\n\n## 0.1.0\n\n- Fixture release.\n')
        self.write('LICENSE-MIT', 'MIT fixture\n')
        self.write('LICENSE-APACHE', 'Apache fixture\n')
        self.write('THIRD_PARTY_NOTICES.md', 'Third party fixture\n')
        self.write('docs/ROADMAP.md', ROADMAP)
        self.write('docs/COMPARISON.md', '# Comparison\n\nAIL commit `abcdef1`; date 2026-11-05; 10 tasks.\n')
        self.write('DIFFERENCES.md', DIFFERENCES)
        self.commit('fixture base')
        self.integrate('alpha')

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def write(self, relative, text):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', message)

    def integrate(self, job):
        self.git('commit', '-q', '--allow-empty', '-m', 'integrate %s (job-%s-1)' % (job, job))

    def run_check(self, *args, branch='main'):
        return subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.repo), '--branch', branch,
                               *args], capture_output=True, text=True, timeout=120)

    def statuses(self, result):
        rows = {}
        for line in result.stdout.splitlines():
            if len(line) > 3 and line[:4] in ('PASS', 'FAIL', 'INFO', 'SKIP'):
                rows[int(line.split()[1])] = line
        return rows

    def add_final_version(self):
        self.write('packaging/ail_lang/__init__.py', '__version__ = "0.1.0"\n')
        self.commit('final version')

    def make_release_ready(self):
        self.add_final_version()
        self.write('DIFFERENCES.md', DIFFERENCES.replace('| open |', '| fixed |'))
        self.commit('close differences')
        self.integrate('beta')

    def test_dev_version_fails_check_one(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stderr)
        row = self.statuses(result)[1]
        self.assertTrue(row.startswith('FAIL'), row)
        self.assertIn('0.1.0.dev0 is a development version', row)

    def test_final_version_passes_check_one(self):
        self.add_final_version()
        result = self.run_check()
        row = self.statuses(result)[1]
        self.assertTrue(row.startswith('PASS'), row)
        self.assertIn('0.1.0 is a final release', row)

    def test_changelog_rejects_prerelease_heading_for_final_version(self):
        self.add_final_version()
        self.write('CHANGELOG.md', '# Changelog\n\n## 0.1.0.dev0\n\n- Pre-release.\n')
        self.commit('pre-release heading')
        row = self.statuses(self.run_check())[2]
        self.assertTrue(row.startswith('FAIL'), row)
        self.assertIn('no heading for 0.1.0', row)

    def test_changelog_accepts_v_prefixed_heading(self):
        self.add_final_version()
        self.write('CHANGELOG.md', '# Changelog\n\n## v0.1.0\n\n- Release.\n')
        self.commit('v-prefixed heading')
        row = self.statuses(self.run_check())[2]
        self.assertTrue(row.startswith('PASS'), row)
        self.assertIn('has a heading for 0.1.0', row)

    def test_local_version_label_is_a_final_release(self):
        for version in ('0.1.0+local', '0.1.0+ubuntu'):
            self.write('packaging/ail_lang/__init__.py', '__version__ = "%s"\n' % version)
            self.commit('local version ' + version)
            row = self.statuses(self.run_check())[1]
            self.assertTrue(row.startswith('PASS'), row)
            self.assertIn('%s is a final release' % version, row)

    def test_annotated_release_tag_on_main_passes(self):
        self.make_release_ready()
        self.git('tag', '-a', 'v0.1.0', '-m', 'release')
        result = self.run_check('--remote', '')
        row = self.statuses(result)[9]
        self.assertTrue(row.startswith('PASS'), row)
        self.assertIn('points at main', row)

    def test_missing_p0_merge_fails_and_names_the_job(self):
        result = self.run_check()
        row = self.statuses(result)[5]
        self.assertTrue(row.startswith('FAIL'), row)
        self.assertIn('beta', row)
        self.assertNotIn('alpha', row)

    def test_two_open_differences_rows_report_two(self):
        result = self.run_check()
        row = self.statuses(result)[7]
        self.assertTrue(row.startswith('FAIL'), row)
        self.assertIn('2 open or empty rows in DIFFERENCES.md', row)

    def test_exit_status_is_one_when_a_check_fails(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn('fail', result.stdout.splitlines()[-1])

    def test_all_pass_repository_exits_zero(self):
        self.make_release_ready()
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.statuses(result)[1].startswith('PASS'))
        self.assertTrue(self.statuses(result)[5].startswith('PASS'))
        self.assertTrue(self.statuses(result)[7].startswith('PASS'))
        self.assertIn('0 fail', result.stdout.splitlines()[-1])

    def test_json_report_parses(self):
        result = self.run_check('--json')
        report = json.loads(result.stdout)
        self.assertGreaterEqual(len(report['checks']), 10)
        self.assertEqual([check['number'] for check in report['checks']], list(range(1, 12)))
        self.assertEqual(report['checks'][0]['status'], 'FAIL')
        self.assertEqual(report['fail'], sum(1 for check in report['checks'] if check['status'] == 'FAIL'))
        self.assertIn('fail', report['summary'])

    def test_output_has_at_least_ten_checks_and_a_summary(self):
        result = self.run_check()
        rows = self.statuses(result)
        self.assertGreaterEqual(len(rows), 10)
        self.assertRegex(result.stdout.splitlines()[-1], r'^\d+ pass, \d+ fail, \d+ info/skip$')


if __name__ == '__main__':
    unittest.main()
