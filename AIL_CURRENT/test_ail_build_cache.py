"""G3 build cache: hits and misses, invalidation, corruption, concurrency, identical output.

Every test runs with its own temporary AIL_CACHE, so a warm cache from another run (or another
test) never changes what is measured. A recording wrapper stands in for the C compiler; the number
of compile lines it logged says whether the compiler ran.
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
EXAMPLES = ROOT / 'language_examples'
SPEC = importlib.util.spec_from_file_location('buildcache_under_test', ROOT / 'python/pkg-v12/buildcache.py')
buildcache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(buildcache)

TYPED = 'fn main()->int {\n    print("cache ok");\n    return 0;\n}\n'
TYPED2 = 'fn main()->int {\n    print("cache changed");\n    return 0;\n}\n'
# Two source texts that name one typed local differently; the generated C is identical.
RENAMED_LOCAL = 'fn main()->int {\n    let %s: int = 1;\n    print(%s);\n    return 0;\n}\n'
SCRIPT = 'print(True)\n'
REAL_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') or shutil.which('cc')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(REAL_CC and os.name != 'nt', 'POSIX with an installed C compiler required')
class CacheBase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-cache-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / 'cache'
        self.log = self.root / 'cc.log'
        self.cc = self.wrapper('cc.sh', '')
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('AIL_') and key != 'PIPE_CC'}
        self.env.update(AIL_CACHE=str(self.cache), PIPE_CC=str(self.cc), CC_LOG=str(self.log), PYTHONUTF8='1')

    def wrapper(self, name, comment):
        path = self.root / name
        path.write_text('#!/bin/sh\n# %s\necho "$*" >> "$CC_LOG"\nexec %s "$@"\n' % (comment, REAL_CC))
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def run_cli(self, *args, env=None, timeout=400):
        return subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), *map(str, args)],
                              capture_output=True, timeout=timeout, env=env or self.env, cwd=self.root)

    def compile(self, source, name, *flags, env=None):
        path = self.root / (name + '.ail')
        if not path.exists() or path.read_text() != source:
            path.write_text(source)
        out = self.root / ('out_' + name + '_' + str(len(list(self.root.glob('out_*')))))
        result = self.run_cli('compile', path, '-o', out, *flags, env=env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return out, result

    def compiles(self):
        """How many times the compiler wrapper compiled or linked something."""
        if not self.log.exists():
            return 0
        return sum(1 for line in self.log.read_text().splitlines() if ' -o ' in ' ' + line + ' ')

    def finished(self):
        """Number of whole-build ("fe") entries in the cache."""
        return len([p for p in (self.cache / 'fe').rglob('*') if p.is_file()]) if (self.cache / 'fe').exists() else 0

    def stats(self):
        result = self.run_cli('cache', 'stats')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def run_exe(self, exe):
        return subprocess.run([str(exe)], capture_output=True, timeout=30).stdout


class CompileCacheTests(CacheBase):
    def test_miss_then_hit_is_byte_identical_and_skips_the_compiler(self):
        first, _ = self.compile(TYPED, 'prog')
        cold = self.compiles()
        self.assertGreaterEqual(cold, 1)
        self.assertGreaterEqual(self.stats()['entries'], 2)       # the cc step and the finished build
        second, _ = self.compile(TYPED, 'prog')
        self.assertEqual(self.compiles(), cold, 'a hit must not run the compiler')
        self.assertEqual(sha(first), sha(second))
        self.assertEqual(self.run_exe(second), b'cache ok\n')
        self.assertTrue(os.access(second, os.X_OK))
        self.assertEqual(second.stat().st_mode & 0o111, first.stat().st_mode & 0o111)

    def test_output_is_identical_with_cache_off(self):
        cached, _ = self.compile(TYPED, 'prog')
        warm, _ = self.compile(TYPED, 'prog')
        off_env = dict(self.env, AIL_NO_CACHE='1')
        off, _ = self.compile(TYPED, 'prog', env=off_env)
        flag, _ = self.compile(TYPED, 'prog', '--no-cache')
        self.assertEqual({sha(cached), sha(warm)}, {sha(off)})
        self.assertEqual(sha(off), sha(flag))

    def test_no_cache_switches_write_nothing_and_always_compile(self):
        for env, flags in ((dict(self.env, AIL_NO_CACHE='1'), ()), (self.env, ('--no-cache',))):
            before = self.compiles()
            self.compile(TYPED, 'prog', *flags, env=env)
            self.compile(TYPED, 'prog', *flags, env=env)
            self.assertEqual(self.compiles() - before, 2)
        self.assertEqual(self.stats()['entries'], 0)

    def test_source_change_misses_and_gives_the_new_program(self):
        self.compile(TYPED, 'prog')
        before = self.compiles()
        changed, _ = self.compile(TYPED2, 'prog')
        self.assertGreater(self.compiles(), before)
        self.assertEqual(self.run_exe(changed), b'cache changed\n')
        again, _ = self.compile(TYPED, 'prog')            # the first version is still cached
        self.assertEqual(self.run_exe(again), b'cache ok\n')

    def test_changed_source_with_the_same_generated_c_hits_the_cc_cache(self):
        """A new source text (so a new whole-build key) whose C is unchanged reuses the binary."""
        first, _ = self.compile(RENAMED_LOCAL % ('value', 'value'), 'prog')
        finished, before = self.finished(), self.compiles()
        renamed, _ = self.compile(RENAMED_LOCAL % ('other', 'other'), 'prog')
        self.assertEqual(self.finished(), finished + 1)   # the merged source is a new front-end entry
        self.assertEqual(self.compiles(), before)         # ... but the C compiler step is reused
        self.assertEqual(sha(first), sha(renamed))
        self.assertEqual(self.run_exe(renamed), b'1\n')

    def test_flag_change_misses(self):
        dynamic, _ = self.compile(TYPED, 'prog')
        before = self.compiles()
        static, _ = self.compile(TYPED, 'prog', '--static')
        self.assertGreater(self.compiles(), before)
        self.assertNotEqual(sha(dynamic), sha(static))
        before = self.compiles()
        self.compile(TYPED, 'prog', '--static')
        self.assertEqual(self.compiles(), before)
        # An AIL_* setting is part of the key of the finished build. The C text is the same, so the
        # compiler step still hits.
        entries = self.finished()
        self.compile(TYPED, 'prog', env=dict(self.env, AIL_NO_GENERAL='1'))
        self.assertEqual(self.finished(), entries + 1)
        self.assertEqual(self.compiles(), before)

    def test_compiler_change_misses(self):
        self.compile(TYPED, 'prog')
        before = self.compiles()
        other = self.wrapper('cc2.sh', 'a different compiler')
        built, _ = self.compile(TYPED, 'prog', env=dict(self.env, PIPE_CC=str(other)))
        self.assertGreater(self.compiles(), before)
        self.assertEqual(self.run_exe(built), b'cache ok\n')

    def test_compiler_source_change_misses(self):
        """Editing any pkg-v12 file is a new compiler: a copy of the tree with one byte changed."""
        copy = self.root / 'sdk'
        copy.mkdir()
        for path in ROOT.glob('*.py'):
            if not path.name.startswith('test_'):
                shutil.copy(path, copy / path.name)
        shutil.copytree(ROOT / 'python', copy / 'python', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(EXAMPLES, copy / 'language_examples', ignore=shutil.ignore_patterns('*.baseline.c'))
        source = self.root / 'prog.ail'
        source.write_text(TYPED)

        def build(tag):
            out = self.root / tag
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(copy / 'ail_chatgpt.py'), 'compile', str(source),
                                     '-o', str(out)], capture_output=True, timeout=400, env=self.env, cwd=self.root)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            return out
        build('a')
        before, entries = self.compiles(), self.finished()
        build('b')
        self.assertEqual((self.compiles(), self.finished()), (before, entries))
        with open(copy / 'python/pkg-v12/pipeline.py', 'a') as handle:
            handle.write('\n# edited\n')
        build('c')
        self.assertEqual(self.finished(), entries + 1)       # the whole build is redone ...
        self.assertEqual(self.compiles(), before)            # ... and the unchanged C still hits the compiler step

    def test_general_path_note_is_replayed_on_a_hit(self):
        path = self.root / 'script.ail'
        path.write_text(SCRIPT)
        runs = []
        for tag in ('one', 'two'):
            out = self.root / ('script_' + tag)
            result = self.run_cli('compile', path, '-o', out)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            runs.append((result.stderr.replace(str(out).encode(), b'OUT'), result.stdout.replace(str(out).encode(), b'OUT'), sha(out)))
        self.assertIn(b'general path', runs[0][0])
        self.assertEqual(runs[0], runs[1])

    def test_failed_build_is_not_cached(self):
        path = self.root / 'bad.ail'
        path.write_text('fn main()->int {\n    return undefined_name;\n}\n')
        for _ in range(2):
            result = self.run_cli('compile', path, '-o', self.root / 'bad_out')
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.stats()['entries'], 0)

    def test_corrupt_entries_are_discarded_and_rebuilt(self):
        good, _ = self.compile(TYPED, 'prog')
        files = [p for p in self.cache.rglob('*') if p.is_file() and len(p.name) == 64]
        self.assertGreaterEqual(len(files), 2)
        for index, path in enumerate(files):
            data = path.read_bytes()
            if index % 3 == 0:
                path.write_bytes(data[:len(data) // 2])                    # truncated
            elif index % 3 == 1:
                path.write_bytes(data[:-5] + bytes(b ^ 0xFF for b in data[-5:]))   # flipped payload bytes
            else:
                path.write_bytes(b'garbage')                               # not an entry at all
        again, _ = self.compile(TYPED, 'prog')
        self.assertEqual(sha(good), sha(again))
        self.assertEqual(self.run_exe(again), b'cache ok\n')
        before = self.compiles()
        third, _ = self.compile(TYPED, 'prog')                              # healed: a hit again
        self.assertEqual(self.compiles(), before)
        self.assertEqual(sha(good), sha(third))

    def test_unwritable_cache_is_not_an_error(self):
        blocker = self.root / 'not_a_directory'
        blocker.write_text('x')
        built, _ = self.compile(TYPED, 'prog', env=dict(self.env, AIL_CACHE=str(blocker / 'sub')))
        self.assertEqual(self.run_exe(built), b'cache ok\n')

    def test_concurrent_builds_share_one_cache(self):
        path = self.root / 'prog.ail'
        path.write_text(TYPED)
        processes = []
        for index in range(4):
            command = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path),
                       '-o', str(self.root / ('par%d' % index))]
            processes.append(subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env))
        for process in processes:
            _, error = process.communicate(timeout=600)
            self.assertEqual(process.returncode, 0, error.decode(errors='replace'))
        digests = {sha(self.root / ('par%d' % index)) for index in range(4)}
        self.assertEqual(len(digests), 1)
        self.assertFalse([p for p in self.cache.rglob('.tmp-*')], 'no temp files left behind')
        before = self.compiles()
        self.compile(TYPED, 'prog')
        self.assertEqual(self.compiles(), before)

    def test_cache_commands(self):
        self.assertEqual(self.run_cli('cache', 'path').stdout.decode().strip(), str(self.cache))
        self.compile(TYPED, 'prog')
        self.assertGreater(self.stats()['entries'], 0)
        cleared = json.loads(self.run_cli('cache', 'clear').stdout)
        self.assertGreater(cleared['removed'], 0)
        self.assertEqual(self.stats()['entries'], 0)
        before = self.compiles()
        self.compile(TYPED, 'prog')                       # still works, and compiles again
        self.assertGreater(self.compiles(), before)

    def test_default_location_follows_xdg(self):
        env = {key: value for key, value in self.env.items() if key != 'AIL_CACHE'}
        env['XDG_CACHE_HOME'] = str(self.root / 'xdg')
        self.assertEqual(self.run_cli('cache', 'path', env=env).stdout.decode().strip(), str(self.root / 'xdg' / 'ail'))

    def test_corpus_programs_are_identical_cold_warm_and_uncached(self):
        names = ('hello', 'binary_cursor_records_main')
        results = {}
        for label, env in (('off', dict(self.env, AIL_NO_CACHE='1')), ('cold', self.env), ('warm', self.env)):
            for name in names:
                out = self.root / ('%s_%s' % (label, name))
                result = self.run_cli('compile', EXAMPLES / (name + '.ail'), '-o', out, env=env)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                results[label, name] = (sha(out), result.stderr.replace(str(out).encode(), b'OUT'))
        for name in names:
            self.assertEqual(results['off', name], results['cold', name])
            self.assertEqual(results['off', name], results['warm', name])


class CompileCCacheTests(CacheBase):
    def make(self, name='c_interop'):
        shutil.copy(EXAMPLES / (name + '.c'), self.root / (name + '.c'))
        shutil.copy(EXAMPLES / (name + '.json'), self.root / (name + '.json'))
        return self.root / (name + '.c'), self.root / (name + '.json')

    def build(self, c, interface, tag, env=None):
        out = self.root / (tag + '.o')
        result = self.run_cli('compile-c', c, '--interface', interface, '-o', out, env=env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return out

    def test_adapter_object_hit_is_identical_and_skips_the_compiler(self):
        c, interface = self.make()
        off = self.build(c, interface, 'off', env=dict(self.env, AIL_NO_CACHE='1'))
        miss = self.build(c, interface, 'miss')
        before = self.compiles()
        hit = self.build(c, interface, 'hit')
        self.assertEqual(self.compiles(), before)
        for other in (miss, hit):
            self.assertEqual(off.read_bytes(), other.read_bytes())
            self.assertEqual(Path(str(off) + '.json').read_bytes(), Path(str(other) + '.json').read_bytes())

    def test_changed_c_source_or_interface_misses(self):
        c, interface = self.make()
        first = self.build(c, interface, 'a')
        before = self.compiles()
        c.write_text(c.read_text() + '\n/* edited */\nint64_t native_extra(void) { return 7; }\n')
        second = self.build(c, interface, 'b')
        self.assertGreater(self.compiles(), before)
        self.assertNotEqual(first.read_bytes(), second.read_bytes())
        before = self.compiles()
        data = json.loads(interface.read_text())
        data['functions']['byte_count']['symbol'] = 'native_byte_count'
        data['functions']['renamed'] = data['functions'].pop('weighted_checksum')
        interface.write_text(json.dumps(data))
        self.build(c, interface, 'c')
        self.assertGreater(self.compiles(), before)

    def test_declared_header_content_is_part_of_the_key(self):
        directory = self.root / 'hdr'
        (directory / 'detail').mkdir(parents=True)
        for source in (EXAMPLES / 'c_headers').rglob('*'):
            if source.is_file():
                target = directory / source.relative_to(EXAMPLES / 'c_headers')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, target)
        c, interface = directory / 'checksum.c', directory / 'checksum.json'
        first = self.build(c, interface, 'h1')
        before = self.compiles()
        self.build(c, interface, 'h2')
        self.assertEqual(self.compiles(), before)
        constants = directory / 'detail' / 'crc_constants.h'
        constants.write_text(constants.read_text() + '\n#define AIL_CACHE_TEST_EDIT 1\n')
        header = directory / 'crc32.h'
        header.write_text(header.read_text().replace('0xEDB88320', '0xEDB88321') if '0xEDB88320' in header.read_text()
                          else header.read_text() + '\n/* edited */\n')
        third = self.build(c, interface, 'h3')
        self.assertGreater(self.compiles(), before)
        self.assertNotEqual(first.read_bytes(), third.read_bytes())


class CcLayerTests(unittest.TestCase):
    """buildcache.run_cc directly, on small C files."""

    def setUp(self):
        if not REAL_CC or os.name == 'nt':
            self.skipTest('POSIX with an installed C compiler required')
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-cc-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        patcher = mock.patch.dict(os.environ, {'AIL_CACHE': str(self.root / 'cache'), 'PIPE_CC': REAL_CC})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('AIL_NO_CACHE', None)
        self.addCleanup(setattr, buildcache, '_active', buildcache._active)
        buildcache._active = True
        self.runs = 0
        self.cwd = None

    def runner(self, command):
        self.runs += 1
        return subprocess.run(command, capture_output=True, text=True, cwd=self.cwd)

    def cc(self, *arguments, cwd=None):
        self.cwd = cwd
        return buildcache.run_cc([REAL_CC, *arguments], self.runner, cwd=cwd)

    def source(self, text, name='a.c'):
        path = self.root / name
        path.write_text(text)
        return path

    def test_hit_restores_the_output_and_skips_the_runner(self):
        c = self.source('int main(void){return 3;}\n')
        out = self.root / 'a.out'
        self.assertEqual(self.cc('-O2', '-o', str(out), str(c)).returncode, 0)
        built = out.read_bytes()
        out.unlink()
        self.assertEqual(self.runs, 1)
        self.assertEqual(self.cc('-O2', '-o', str(out), str(c)).returncode, 0)
        self.assertEqual(self.runs, 1)
        self.assertEqual(out.read_bytes(), built)
        self.assertEqual(subprocess.run([str(out)]).returncode, 3)
        self.assertTrue(os.access(out, os.X_OK))

    def test_inputs_and_flags_are_part_of_the_key(self):
        c = self.source('int main(void){return 3;}\n')
        out = self.root / 'a.out'
        self.cc('-O2', '-o', str(out), str(c))
        self.cc('-O0', '-o', str(out), str(c))
        self.assertEqual(self.runs, 2)
        c.write_text('int main(void){return 4;}\n')
        self.cc('-O2', '-o', str(out), str(c))
        self.assertEqual(self.runs, 3)
        self.assertEqual(subprocess.run([str(out)]).returncode, 4)
        c.write_text('int main(void){return 3;}\n')
        self.cc('-O2', '-o', str(out), str(c))
        self.assertEqual(self.runs, 3)                     # the first version is still cached
        self.assertEqual(subprocess.run([str(out)]).returncode, 3)

    def test_a_header_outside_the_working_directory_is_revalidated(self):
        include = self.root / 'inc'
        include.mkdir()
        header = include / 'value.h'
        header.write_text('#define VALUE 5\n')
        c = self.source('#include "value.h"\nint main(void){return VALUE;}\n')
        out = self.root / 'a.out'
        self.cc('-I', str(include), '-o', str(out), str(c))
        self.cc('-I', str(include), '-o', str(out), str(c))
        self.assertEqual(self.runs, 1)
        header.write_text('#define VALUE 9\n')                # same size, new content
        self.cc('-I', str(include), '-o', str(out), str(c))
        self.assertEqual(self.runs, 2)
        self.assertEqual(subprocess.run([str(out)]).returncode, 9)
        header.unlink()                                      # a vanished header is a miss, then the real error
        result = self.cc('-I', str(include), '-o', str(out), str(c))
        self.assertNotEqual(result.returncode, 0)

    def test_include_directory_inside_the_working_directory_is_hashed(self):
        work = self.root / 'work'
        (work / 'inputs').mkdir(parents=True)
        (work / 'inputs' / 'value.h').write_text('#define VALUE 5\n')
        (work / 'a.c').write_text('#include "value.h"\nint main(void){return VALUE;}\n')
        command = ['-I', 'inputs', '-MD', '-MF', str(work / 'a.d'), '-MT', 'unit', '-c', 'a.c', '-o', str(work / 'a.o')]
        self.cc(*command, cwd=str(work))
        (work / 'a.d').unlink()
        self.cc(*command, cwd=str(work))
        self.assertEqual(self.runs, 1)
        self.assertIn('inputs/value.h', (work / 'a.d').read_text())     # the depfile comes back too
        (work / 'inputs' / 'value.h').write_text('#define VALUE 6\n')
        self.cc(*command, cwd=str(work))
        self.assertEqual(self.runs, 2)

    def test_failures_are_not_cached(self):
        c = self.source('int main(void){ return ; ;; broken\n')
        out = self.root / 'a.out'
        for _ in range(2):
            self.assertNotEqual(self.cc('-o', str(out), str(c)).returncode, 0)
        self.assertEqual(self.runs, 2)
        self.assertEqual(buildcache.stats()['entries'], 0)

    def test_cache_off_runs_the_compiler_every_time(self):
        c = self.source('int main(void){return 3;}\n')
        out = self.root / 'a.out'
        with mock.patch.dict(os.environ, {'AIL_NO_CACHE': '1'}):
            self.cc('-o', str(out), str(c))
            self.cc('-o', str(out), str(c))
        self.assertEqual(self.runs, 2)
        buildcache._active = False
        self.cc('-o', str(out), str(c))
        self.cc('-o', str(out), str(c))
        self.assertEqual(self.runs, 4)

    def test_corrupt_entry_is_a_miss_and_is_removed(self):
        c = self.source('int main(void){return 3;}\n')
        out = self.root / 'a.out'
        self.cc('-o', str(out), str(c))
        [entry] = [p for p in (self.root / 'cache').rglob('*') if p.is_file() and len(p.name) == 64]
        entry.write_bytes(entry.read_bytes()[:40])
        self.cc('-o', str(out), str(c))
        self.assertEqual(self.runs, 2)
        self.assertEqual(subprocess.run([str(out)]).returncode, 3)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-store-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        patcher = mock.patch.dict(os.environ, {'AIL_CACHE': str(self.root / 'cache')})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('AIL_NO_CACHE', None)

    def test_round_trip_and_miss(self):
        key = buildcache.digest('a', b'b')
        self.assertIsNone(buildcache.get('fe', key))
        self.assertTrue(buildcache.put('fe', key, b'payload'))
        self.assertEqual(buildcache.get('fe', key), b'payload')
        self.assertNotEqual(buildcache.digest('a', b'b'), buildcache.digest('ab', b''))      # parts are delimited

    def test_least_recently_used_entries_go_first(self):
        keys = [buildcache.digest('k', i) for i in range(6)]
        for index, key in enumerate(keys):
            buildcache.put('fe', key, bytes([index]) * 100_000)
            os.utime(buildcache._entry_path('fe', key), (1000 + index, 1000 + index))
        self.assertIsNotNone(buildcache.get('fe', keys[0]))          # touching key 0 makes it the newest
        removed = buildcache.trim(limit=300_000)
        self.assertGreaterEqual(removed, 3)
        self.assertIsNotNone(buildcache.get('fe', keys[0]))
        self.assertIsNone(buildcache.get('fe', keys[1]))
        self.assertLessEqual(buildcache.stats()['bytes'], 300_000)

    def test_size_bound_is_applied_on_put(self):
        with mock.patch.dict(os.environ, {'AIL_CACHE_MAX_MB': '0.25'}):
            for index in range(8):
                buildcache.put('fe', buildcache.digest('s', index), bytes(100_000))
                (self.root / 'cache' / '.trimmed').unlink(missing_ok=True)      # let every put trim
            self.assertLessEqual(buildcache.stats()['bytes'], 262_144)
            self.assertGreaterEqual(buildcache.stats()['entries'], 1)

    def test_concurrent_writers_and_readers_never_see_a_partial_entry(self):
        script = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('bc', sys.argv[1]); m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "worker = int(sys.argv[2]); bad = 0\n"
            "for i in range(150):\n"
            "    key = m.digest('shared', i % 5)\n"
            "    payload = (bytes([worker]) * (1000 + 5000 * (i % 7)))\n"
            "    m.put('fe', key, payload)\n"
            "    got = m.get('fe', key)\n"
            "    if got is not None and (len(set(got)) != 1):\n"
            "        bad += 1\n"
            "sys.exit(bad)\n")
        processes = [subprocess.Popen([sys.executable, '-c', script, str(ROOT / 'python/pkg-v12/buildcache.py'), str(n)],
                                      env=dict(os.environ)) for n in range(5)]
        self.assertEqual([p.wait(timeout=300) for p in processes], [0] * 5)
        self.assertEqual([p for p in (self.root / 'cache').rglob('.tmp-*')], [])

    def test_clear_only_removes_cache_directories(self):
        buildcache.put('fe', buildcache.digest('x'), b'1')
        buildcache.put('cc', buildcache.digest('y'), b'2')
        keep = self.root / 'cache' / 'user_file.txt'
        keep.write_text('mine')
        self.assertEqual(buildcache.clear(), 2)
        self.assertEqual(buildcache.stats()['entries'], 0)
        self.assertTrue(keep.exists())


if __name__ == '__main__':
    unittest.main()
