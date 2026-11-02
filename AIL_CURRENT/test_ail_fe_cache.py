"""The opt-in front-end cache: hits, misses, invalidation, corruption, concurrency, identical C.

Each test uses its own cache directory and a recording C compiler that saves every .c file it
is given, so a hit can be compared byte for byte with a fresh build and the cache log says
whether the Python lowering was skipped.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
REAL_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') or shutil.which('cc')
SPEC = importlib.util.spec_from_file_location('fecache_under_test', ROOT / 'python/pkg-v12/fecache.py')
fecache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fecache)

SOURCE = '''\
def add(a: int, b: int) -> int:
    return a + b

def main() -> None:
    print(add(2, 3))

main()
'''
SOURCE2 = SOURCE.replace('print(add(2, 3))', 'print(add(20, 30))')
IMPORTED = '''\
def value() -> int:
    return 7
'''
IMPORT_MAIN = '''\
from lib import value

def main() -> None:
    print(value())

main()
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files_hash(directory):
    h = hashlib.sha256()
    for data in sorted(path.read_bytes() for path in Path(directory).glob('*')):
        h.update(len(data).to_bytes(8, 'little') + data)
    return h.hexdigest()


@unittest.skipUnless(REAL_CC and os.name != 'nt', 'POSIX with an installed C compiler required')
class CacheBase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-fe-cache-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / 'fe'
        self.log = self.root / 'fe.log'
        self.patch = mock.patch.dict(os.environ, {'AIL_FE_CACHE_DIR': str(self.cache)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.cc = self.wrapper()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('AIL_') and key != 'PIPE_CC'}
        self.env.update(AIL_NO_CACHE='1', AIL_FE_CACHE='1', AIL_FE_CACHE_DIR=str(self.cache),
                        AIL_FE_CACHE_LOG=str(self.log), AIL_SERVER='0', PIPE_CC=str(self.cc),
                        CC_LOG=str(self.root / 'cc.log'), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        self.counter = 0

    def wrapper(self):
        path = self.root / 'cc.sh'
        path.write_text('#!/bin/sh\n'
                        'echo "$*" >> "$CC_LOG"\n'
                        'for a in "$@"; do case "$a" in *.c) f=$(mktemp "$CC_SAVE/c.XXXXXX"); cp "$a" "$f";; esac; done\n'
                        'exec %s "$@"\n' % REAL_CC)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def run_cli(self, *args, env=None, timeout=400):
        return subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), *map(str, args)],
                              capture_output=True, timeout=timeout, env=env or self.env, cwd=self.root)

    def compile(self, source, name='prog', *flags, env=None):
        path = self.root / (name + '.py')
        path.write_text(source)
        self.counter += 1
        out = self.root / ('out%d' % self.counter)
        saved = self.root / ('c%d' % self.counter)
        saved.mkdir()
        run_env = dict(self.env if env is None else env, CC_SAVE=str(saved))
        result = self.run_cli('compile', path, '--syntax', 'python', '-o', out, *flags, env=run_env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return out, saved

    def events(self):
        if not self.log.exists():
            return []
        return [line.split() for line in self.log.read_text().splitlines() if line.strip()]

    def last_event(self):
        events = self.events()
        return events[-1] if events else []

    def entries(self):
        return fecache.entries() if self.cache.exists() else []


class FrontEndCacheTests(CacheBase):
    def test_miss_then_hit_is_identical_and_skips_lowering(self):
        first, c1 = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'miss')
        second, c2 = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'hit')
        self.assertEqual(sha(first), sha(second))
        self.assertEqual(files_hash(c1), files_hash(c2))
        self.assertEqual(subprocess.run([str(second)], capture_output=True).stdout, b'5\n')
        self.assertEqual(len(self.entries()), 1)

    def test_source_change_misses_and_gives_the_new_program(self):
        self.compile(SOURCE)
        changed, saved = self.compile(SOURCE2)
        self.assertEqual(self.last_event()[0], 'miss')
        self.assertEqual(subprocess.run([str(changed)], capture_output=True).stdout, b'50\n')
        self.assertGreaterEqual(len(self.entries()), 2)
        again, _ = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'hit')
        self.assertEqual(subprocess.run([str(again)], capture_output=True).stdout, b'5\n')

    def test_import_change_misses(self):
        (self.root / 'lib.py').write_text(IMPORTED)
        self.compile(IMPORT_MAIN, 'main')
        self.assertEqual(self.last_event()[0], 'miss')
        (self.root / 'lib.py').write_text(IMPORTED.replace('7', '9'))
        changed, _ = self.compile(IMPORT_MAIN, 'main')
        self.assertEqual(self.last_event()[0], 'miss')
        self.assertEqual(subprocess.run([str(changed)], capture_output=True).stdout, b'9\n')

    def test_flag_change_misses(self):
        self.compile(SOURCE)
        self.compile(SOURCE, 'prog', '--static')
        self.assertEqual(self.last_event()[0], 'miss')
        self.compile(SOURCE, 'prog', '--static')
        self.assertEqual(self.last_event()[0], 'hit')

    def test_environment_change_misses(self):
        self.compile(SOURCE)
        self.compile(SOURCE, 'prog', env=dict(self.env, AIL_EXTRA_CFLAGS='-DAIL_FE_CACHE_TEST=1'))
        self.assertEqual(self.last_event()[0], 'miss')
        self.compile(SOURCE, 'prog', env=dict(self.env, AIL_EXTRA_CFLAGS='-DAIL_FE_CACHE_TEST=1'))
        self.assertEqual(self.last_event()[0], 'hit')

    def test_compiler_file_change_misses(self):
        copy = self.root / 'sdk'
        copy.mkdir()
        for path in ROOT.glob('*.py'):
            if not path.name.startswith('test_'):
                shutil.copy2(path, copy / path.name)
        shutil.copytree(ROOT / 'python', copy / 'python', ignore=shutil.ignore_patterns('__pycache__'))
        source = self.root / 'prog.py'
        source.write_text(SOURCE)

        def build(tag):
            out = self.root / tag
            saved = self.root / (tag + '-c')
            saved.mkdir()
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(copy / 'ail_chatgpt.py'),
                                     'compile', str(source), '--syntax', 'python', '-o', str(out)],
                                    capture_output=True, timeout=400,
                                    env=dict(self.env, CC_SAVE=str(saved)), cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            return out, saved

        first, c1 = build('one')
        self.assertEqual(self.last_event()[0], 'miss')
        with open(copy / 'python' / 'pkg-v12' / 'pyc.py', 'a') as handle:
            handle.write('\n')
        second, c2 = build('two')
        self.assertEqual(self.last_event()[0], 'miss')
        self.assertEqual(sha(first), sha(second))
        self.assertEqual(files_hash(c1), files_hash(c2))

    def test_corrupt_and_truncated_entries_fall_back(self):
        first, c1 = self.compile(SOURCE)
        key = self.last_event()[1]
        entry = fecache._entry_path(key)
        entry.write_bytes(entry.read_bytes()[:12])
        second, c2 = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'miss')
        self.assertEqual(sha(first), sha(second))
        self.assertEqual(files_hash(c1), files_hash(c2))
        entry.write_bytes(b'AILFEC1\n' + b'0' * 64 + b'\n' + b'not the payload')
        third, c3 = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'miss')
        self.assertEqual(sha(first), sha(third))
        self.assertEqual(files_hash(c1), files_hash(c3))
        self.assertIn(key, [event[1] for event in self.events() if len(event) > 1])

    def test_concurrent_builds_do_not_corrupt_the_cache(self):
        source = self.root / 'prog.py'
        source.write_text(SOURCE)
        processes, saved = [], []
        for index in range(2):
            out = self.root / ('concurrent%d' % index)
            directory = self.root / ('concurrent-c%d' % index)
            directory.mkdir()
            saved.append(directory)
            processes.append(subprocess.Popen(
                [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                 '--syntax', 'python', '-o', str(out)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=dict(self.env, CC_SAVE=str(directory)), cwd=self.root))
        results = [process.communicate(timeout=400) for process in processes]
        for process, (_, error) in zip(processes, results):
            self.assertEqual(process.returncode, 0, error.decode(errors='replace'))
        self.assertEqual(files_hash(saved[0]), files_hash(saved[1]))
        third, _ = self.compile(SOURCE)
        self.assertEqual(self.last_event()[0], 'hit')
        self.assertEqual(subprocess.run([str(third)], capture_output=True).stdout, b'5\n')

    def test_cache_is_off_by_default(self):
        env = dict(self.env)
        env.pop('AIL_FE_CACHE')
        env.pop('AIL_FE_CACHE_LOG')
        self.compile(SOURCE, env=env)
        self.compile(SOURCE, env=env)
        self.assertFalse(self.cache.exists() and self.entries())
        self.assertEqual(self.events(), [])

    def test_flag_enables_the_cache(self):
        env = dict(self.env)
        env.pop('AIL_FE_CACHE')
        env.pop('AIL_FE_CACHE_LOG')
        saved = self.root / 'flag-c'
        saved.mkdir()
        env['CC_SAVE'] = str(saved)
        source = self.root / 'prog.py'
        source.write_text(SOURCE)
        for index in range(2):
            result = self.run_cli('compile', source, '--syntax', 'python', '--fe-cache',
                                  '-o', self.root / ('flag%d' % index), env=env)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(len(self.entries()), 1)


@unittest.skipUnless(REAL_CC and os.name != 'nt', 'POSIX with an installed C compiler required')
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-fe-store-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = mock.patch.dict(os.environ, {
            'AIL_FE_CACHE_DIR': str(self.root), 'AIL_FE_CACHE_MAX_MB': '1'})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_default_location_follows_xdg(self):
        with mock.patch.dict(os.environ, {'XDG_CACHE_HOME': str(self.root / 'xdg')}):
            os.environ.pop('AIL_FE_CACHE_DIR', None)
            self.assertEqual(fecache.root(), self.root / 'xdg' / 'ail' / 'fe')
            self.assertEqual(fecache.entries_root(), self.root / 'xdg' / 'ail' / 'fe' / 'c')
        self.assertEqual(fecache.max_bytes(), 1 << 20)

    def test_round_trip_corruption_and_least_recently_used(self):
        key = fecache.key('round-trip')
        self.assertIsNone(fecache.get(key))
        self.assertTrue(fecache.put(key, b'payload'))
        self.assertEqual(fecache.get(key), b'payload')
        path = fecache._entry_path(key)
        path.write_bytes(path.read_bytes()[:-1])
        self.assertIsNone(fecache.get(key))
        self.assertFalse(path.exists())

        keys = [fecache.key('lru', index) for index in range(6)]
        for index, item in enumerate(keys):
            fecache.put(item, bytes([index]) * 100_000)
            os.utime(fecache._entry_path(item), (1000 + index, 1000 + index))
        self.assertIsNotNone(fecache.get(keys[0]))
        fecache.trim(limit=300_000)
        self.assertIsNotNone(fecache.get(keys[0]))
        self.assertIsNone(fecache.get(keys[1]))
        self.assertLessEqual(fecache.stats()['bytes'], 300_000)

    def test_clear_only_removes_the_front_end_cache(self):
        fecache.put(fecache.key('clear'), b'1')
        outside = self.root / 'keep.txt'
        outside.write_text('keep')
        self.assertEqual(fecache.clear(), 1)
        self.assertEqual(fecache.stats()['entries'], 0)
        self.assertTrue(outside.exists())
