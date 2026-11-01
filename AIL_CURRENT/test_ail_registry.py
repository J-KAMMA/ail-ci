"""Test registration by file (tests.d/) and sharded manifest pins (manifest.d/).

Two pull requests that each add a test and change a source file must merge without touching a shared
line; these tests build a throwaway git repository and do exactly that.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import ail_check
import ail_manifest

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / 'tools' / 'update_manifest.py'


class Registration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def register(self, name, text=None, stem=None):
        directory = self.root / ail_check.TESTS_DIR
        directory.mkdir(exist_ok=True)
        (directory / f'{stem or name}.txt').write_text(name + '\n' if text is None else text, encoding='utf-8')

    def test_union_is_listed_first_then_sorted_discovered_without_duplicates(self):
        for name in ('test_zeta', 'test_alpha', 'test_listed_b'):
            self.register(name)
        found = ail_check.discover_modules(self.root)
        self.assertEqual(found, ['test_alpha', 'test_listed_b', 'test_zeta'])
        merged = ail_check.merge_modules(('test_listed_b', 'test_listed_a'), found)
        self.assertEqual(merged, ('test_listed_b', 'test_listed_a', 'test_alpha', 'test_zeta'))
        self.assertEqual(ail_check.discover_modules(self.root / 'absent'), [])

    def test_live_union_matches_the_tuple_plus_files(self):
        listed = set(ail_check.LISTED_MODULES)
        self.assertEqual(set(ail_check.MODULES), listed | set(ail_check.discover_modules()))
        self.assertEqual(len(ail_check.MODULES), len(set(ail_check.MODULES)))
        self.assertEqual(list(ail_check.MODULES[:len(ail_check.LISTED_MODULES)]), list(ail_check.LISTED_MODULES))
        self.assertIn('test_ail_registry', ail_check.MODULES)
        self.assertEqual(ail_check.registry_problems(HERE), [])

    def test_registration_problems_are_reported(self):
        (self.root / 'test_good.py').write_text('', encoding='utf-8')
        self.register('test_good')
        self.assertEqual(ail_check.registry_problems(self.root), [])
        self.register('test_other', stem='test_good_name')              # name differs from the file stem
        self.register('test_comment', '# why\ntest_comment\n')          # comment lines are allowed ...
        self.register('test_two', 'test_two\ntest_extra\n')             # ... a second module is not
        self.register('test_missing')                                   # no test_missing.py beside it
        self.register('helper', stem='helper')                          # must start with test_
        (self.root / ail_check.TESTS_DIR / 'test_bad.md').write_text('test_bad\n', encoding='utf-8')
        text = '\n'.join(ail_check.registry_problems(self.root))
        for fragment in ('test_good_name.txt', 'test_two.txt', 'test_missing.txt', 'helper.txt', 'test_bad.md'):
            self.assertIn(fragment, text)
        self.assertNotIn('test_good.txt', text)
        self.assertEqual(len(ail_check.registry_problems(self.root)), 6)   # test_comment is a missing .py as well


class Shards(unittest.TestCase):
    def test_render_parse_round_trip_and_canonical_bucket(self):
        pins = {'b.py': ('b' * 64, 's'), 'a/a.py': ('a' * 64, 'fs'), 'c c.py': ('c' * 64, '')}
        texts = ail_manifest.render(pins)
        for file, text in texts.items():
            for line in text.splitlines():
                self.assertEqual(file, ail_manifest.shard_name(line.split(' ', 2)[2]))
        parsed = {}
        for file, text in texts.items():
            parsed.update(ail_manifest.parse(text, file))
        self.assertEqual(parsed, {'b.py': ('b' * 64, 's'), 'a/a.py': ('a' * 64, 'fs'), 'c c.py': ('c' * 64, '')})

    def test_malformed_and_conflicted_text(self):
        good = 'a' * 64 + ' - x.py\n'
        for bad in ('zz - x.py\n', 'a' * 64 + ' q x.py\n', '<<<<<<< HEAD\n' + good, good + good):
            with self.assertRaises(ValueError):
                ail_manifest.parse(bad)
        merged = ail_manifest.parse('<<<<<<< HEAD\n' + good + '=======\n' + 'b' * 64 + ' s x.py\n>>>>>>> other\n', repair=True)
        self.assertEqual(merged, {'x.py': ('b' * 64, 's')})

    def test_real_manifest_assembles_the_expected_maps(self):
        manifest = ail_manifest.load(HERE)
        self.assertTrue(set(manifest['sdk_files']) <= set(manifest['sha256']))
        self.assertEqual(len(manifest['sdk_files']), len(set(manifest['sdk_files'])))
        self.assertIn('ail_manifest.py', manifest['sdk_files'])
        self.assertNotIn('sha256', json.loads((HERE / 'MANIFEST.json').read_text(encoding='utf-8')))

    def test_plain_manifest_without_shards_is_read_as_is(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'MANIFEST.json').write_text(json.dumps({'sha256': {'x': '1'}, 'sdk_files': ['x']}), encoding='utf-8')
            self.assertEqual(ail_manifest.load(temp), {'sha256': {'x': '1'}, 'sdk_files': ['x']})


def git(repo, *args, check=True):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', '-c', 'commit.gpgsign=false',
                           '-c', 'core.autocrlf=false', *args], cwd=repo, capture_output=True, text=True, check=check)


def other_bucket_names(count):
    """Module-style file names whose pins fall in `count` different shards."""
    chosen, seen = [], set()
    for i in range(1000):
        name = f'src_{i}.py'
        if ail_manifest.shard_name(name) not in seen:
            seen.add(ail_manifest.shard_name(name))
            chosen.append(name)
        if len(chosen) == count:
            return chosen


@unittest.skipUnless(shutil.which('git'), 'git is required')
class ThrowawayRepository(unittest.TestCase):
    """The scenario the layout exists for, in a scratch repository with the real tool and loader."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        (self.repo / 'tools').mkdir(parents=True)
        (self.repo / 'AIL_CURRENT').mkdir()
        shutil.copy(TOOL, self.repo / 'tools' / 'update_manifest.py')
        shutil.copy(HERE / 'ail_manifest.py', self.repo / 'AIL_CURRENT' / 'ail_manifest.py')
        (self.repo / 'AIL_CURRENT' / 'ail_check.py').write_text("LISTED_MODULES = ('test_old',)\n", encoding='utf-8')
        (self.repo / 'AIL_CURRENT' / 'test_old.py').write_text('# old\n', encoding='utf-8')
        self.names = other_bucket_names(3)
        for name in self.names:
            (self.repo / 'AIL_CURRENT' / name).write_text('line 1\nline 2\nline 3\n', encoding='utf-8')
        # a legacy single-file manifest: the first run must convert it
        legacy = {'release': 'r', 'sdk_files': [self.names[0]], 'files': {self.names[0]: 'x'}, 'sha256': {'gone.py': '0' * 64, **{n: '1' * 64 for n in self.names}}}
        (self.repo / 'AIL_CURRENT' / 'MANIFEST.json').write_text(json.dumps(legacy, indent=2) + '\n', encoding='utf-8')
        git(self.repo, 'init', '-q', '-b', 'integ')
        git(self.repo, 'add', '-A')
        self.tool()                       # converts and pins
        self.assertEqual(self.tool('--check').returncode, 0)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'base')

    def tool(self, *args):
        return subprocess.run([sys.executable, str(self.repo / 'tools' / 'update_manifest.py'), *args],
                              cwd=self.repo, capture_output=True, text=True)

    def src(self, name):
        return self.repo / 'AIL_CURRENT' / name

    def test_conversion_kept_every_legacy_pin_and_flag(self):
        manifest = ail_manifest.load(self.repo / 'AIL_CURRENT')
        self.assertEqual(manifest['sdk_files'], [self.names[0]])
        self.assertEqual(manifest['sha256']['gone.py'], '0' * 64)           # historical pins survive
        self.assertIn('test_old.py', manifest['sha256'])
        self.assertEqual(set(manifest['files']), {self.names[0]})
        self.assertNotIn('sha256', json.loads(self.src('MANIFEST.json').read_text(encoding='utf-8')))

    def test_stale_pin_missing_registration_pin_and_noncanonical_shard_fail_the_check(self):
        self.src(self.names[1]).write_text('changed\n', encoding='utf-8')
        result = self.tool('--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('stale ' + self.names[1], result.stdout)
        self.assertEqual(self.tool().returncode, 0)
        self.assertEqual(self.tool('--check').returncode, 0)
        (self.src('test_new.py')).write_text('# new\n', encoding='utf-8')
        (self.src('tests.d')).mkdir()
        (self.src('tests.d') / 'test_new.txt').write_text('test_new\n', encoding='utf-8')
        git(self.repo, 'add', '-A')
        result = self.tool('--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('unpinned test_new.py', result.stdout)
        self.assertIn('unpinned tests.d/test_new.txt', result.stdout)
        self.tool()
        self.assertEqual(self.tool('--check').returncode, 0)
        shard = self.src('manifest.d') / ail_manifest.shard_name('test_new.py')
        shard.write_text(''.join(sorted(shard.read_text(encoding='utf-8').splitlines(True), reverse=True)), encoding='utf-8')
        lines = shard.read_text(encoding='utf-8').splitlines()
        if len(lines) > 1:
            self.assertEqual(self.tool('--check').returncode, 1)          # order is part of the canonical form
        shard.write_text(shard.read_text(encoding='utf-8') + ('\n' if False else ''), encoding='utf-8')
        self.tool()
        self.assertEqual(self.tool('--check').returncode, 0)

    def test_a_regenerated_compiler_source_pin_keeps_the_sdk_flag(self):
        name = 'python/pkg-v12/newmod.py'
        module = self.src(name)
        module.parent.mkdir(parents=True)
        module.write_text('# new compiler module\n', encoding='utf-8')
        git(self.repo, 'add', '-A')
        self.assertEqual(self.tool().returncode, 0)
        pins = ail_manifest.read_pins(self.src('.'))
        self.assertEqual(pins[name][1], 's')
        shard = self.src('manifest.d') / ail_manifest.shard_name(name)
        # An integration merge that keeps the other side of the shard drops this new pin; the next
        # update_manifest run must restore it as an SDK file (test_ail_packaging otherwise fails).
        shard.write_text(''.join(line for line in shard.read_text(encoding='utf-8').splitlines(True)
                                 if name not in line), encoding='utf-8')
        self.assertEqual(self.tool().returncode, 0)
        pins = ail_manifest.read_pins(self.src('.'))
        self.assertEqual(pins[name][1], 's')
        self.assertIn(name, ail_manifest.load(self.src('.'))['sdk_files'])

    def make_branch(self, branch, source, new_test):
        git(self.repo, 'checkout', '-q', '-b', branch, 'integ')
        self.src(source).write_text('line 1\nline 2\nline 3\n' + branch + '\n', encoding='utf-8')
        module = f'test_{new_test}'
        self.src(module + '.py').write_text('# ' + module + '\n', encoding='utf-8')
        (self.src('tests.d')).mkdir(exist_ok=True)
        (self.src('tests.d') / f'{module}.txt').write_text(module + '\n', encoding='utf-8')
        git(self.repo, 'add', '-A')
        self.assertEqual(self.tool().returncode, 0)
        self.assertEqual(self.tool('--check').returncode, 0)
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', branch)

    def test_two_branches_each_adding_a_test_and_changing_a_source_merge_cleanly(self):
        self.make_branch('one', self.names[1], 'one')
        self.make_branch('two', self.names[2], 'two')
        git(self.repo, 'checkout', '-q', 'one')
        merged = git(self.repo, 'merge', '--no-edit', 'two', check=False)
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        result = self.tool('--check')
        self.assertEqual(result.returncode, 0, result.stdout)
        found = ail_check.discover_modules(self.repo / 'AIL_CURRENT')
        self.assertEqual(found, ['test_one', 'test_two'])
        manifest = ail_manifest.load(self.repo / 'AIL_CURRENT')
        for name in ('test_one.py', 'test_two.py', 'tests.d/test_one.txt', 'tests.d/test_two.txt'):
            self.assertIn(name, manifest['sha256'])

    def test_same_file_edited_by_both_branches_conflicts_only_in_one_pin_line_and_is_repaired(self):
        for branch, first in (('one', True), ('two', False)):
            git(self.repo, 'checkout', '-q', '-b', branch, 'integ')
            text = self.src(self.names[1]).read_text(encoding='utf-8').splitlines()
            text[0 if first else 2] = branch                      # different regions: the source merges cleanly
            self.src(self.names[1]).write_text('\n'.join(text) + '\n', encoding='utf-8')
            self.assertEqual(self.tool().returncode, 0)
            git(self.repo, 'add', '-A')
            git(self.repo, 'commit', '-q', '-m', branch)
        git(self.repo, 'checkout', '-q', 'one')
        merged = git(self.repo, 'merge', '--no-edit', 'two', check=False)
        self.assertNotEqual(merged.returncode, 0)
        conflicted = git(self.repo, 'diff', '--name-only', '--diff-filter=U').stdout.split()
        self.assertEqual(conflicted, ['AIL_CURRENT/manifest.d/' + ail_manifest.shard_name(self.names[1])])
        self.assertEqual(self.tool('--check').returncode, 1)
        self.assertEqual(self.tool().returncode, 0)               # markers are tolerated and the pin is recomputed
        self.assertEqual(self.tool('--check').returncode, 0)
        self.assertNotIn('<<<<', (self.src('manifest.d') / ail_manifest.shard_name(self.names[1])).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
