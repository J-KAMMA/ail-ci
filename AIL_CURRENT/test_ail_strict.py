"""Strict mode: build on the typed path or refuse, and say every reason at once.

`ail_chatgpt.py compile --strict` (also `AIL_STRICT=1`, `ail build --strict`, `ail run --strict`) sets
AIL_NO_GENERAL for the build, so a program the typed path cannot take is never built on the general path.
When it refuses, python/pkg-v12/strictmode.py keeps going past the first refusal and lists every blocker:
`file:line:col`, the construct, why it is not typed and a `write instead:` rewrite, the one that keeps the
most code off the typed path first. `--strict --json` prints the same list as `ail.strict/1` JSON.

S1  a program with three different blockers is refused with all three listed, ranked by the code they block
S2  a typed program builds with --strict, with AIL_STRICT=1 and with AIL_NO_GENERAL=1 to the same executable
    bytes as the default build
S3  the JSON shape (schema, counts, one record per blocker, ranks 1..n, the fields an LLM needs to fix it)
S4  the default build of a program that falls back prints the one-line note (about 20x slower, run with
    --strict to see why); AIL_QUIET_FALLBACK=1 silences it; the program still runs
S5  AIL_NO_GENERAL=1 alone keeps its old behaviour (the first refusal only, no list)
S6  the `ail` command: `ail build --strict` lists the blockers, `ail run --strict` runs a typed program
S7  a blocker the compiler reports without a position is still located, and a refusal that is only the
    consequence of an earlier one is not listed
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
REPO = ROOT.parent

THREE = '''def gen(n: int):
    for i in range(n):
        yield i

def total(n: int) -> int:
    s = 0
    for x in gen(n):
        s += x
    return s

def best(words: list[str]) -> int:
    d = {}
    for w in words:
        d[w] = d.get(w, 0) + 1
    top = max(d.items(), key=lambda kv: kv[1])
    return top[1]

def show(xs: list[int]):
    print(xs)

def main():
    print(total(4))
    print(best(["a", "b", "a"]))
    show([1, 2])

main()
'''

TYPED = '''def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps

def main():
    best = 0
    for i in range(1, 200):
        s = collatz(i)
        if s > best:
            best = s
    print(best)

main()
'''

OPTIONAL = '''from typing import Optional

def f(d: dict[int, int], x: int) -> Optional[int]:
    return d.get(x)

def main():
    r = f({3: 3}, 3)
    print(r)

main()
'''

# the compiler refuses `self.next = None` without naming a statement
NO_POSITION = '''class Node:
    def __init__(self, v: int):
        self.v = v
        self.next = None

def main():
    print(1)

main()
'''

# one refusal (the generator) and a caller that only fails because of it
CONSEQUENCE = '''def gen(n: int):
    for i in range(n):
        yield i

def total(n: int) -> int:
    s = 0
    for x in gen(n):
        s += x
    return s

def main():
    r = total(3)
    print(r + 1)

main()
'''

BLOCKER_KEYS = {'rank', 'path', 'line', 'column', 'function', 'statement', 'construct', 'why', 'write_instead',
                'blocks_lines', 'blocks_functions', 'message'}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-strict-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def env(self, **extra):
        env = {key: value for key, value in os.environ.items()
               if key not in ('AIL_NO_GENERAL', 'AIL_QUIET_FALLBACK', 'AIL_STRICT', 'AIL_IR')}
        env.update(extra)
        return env

    def compile(self, text, name='prog', extra=(), **env):
        source = self.dir / (name + '.ail')
        source.write_text(text, encoding='utf-8')
        exe = self.dir / (name + '_exe')
        if exe.exists():
            exe.unlink()
        result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name, '--syntax', 'python',
                                 '-o', exe.name, *extra], cwd=self.dir, capture_output=True, text=True,
                                timeout=900, env=self.env(**env))
        return result, exe


class StrictRefusal(Base):
    def test_s1_three_blockers_are_all_listed_and_ranked(self):
        result, exe = self.compile(THREE, extra=('--strict',))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(exe.exists())
        self.assertEqual(result.stdout, '')
        text = result.stderr
        self.assertTrue(text.startswith('strict: 3 typed-path blockers;'), text)
        # every blocker has file:line:col, the construct, why, and a rewrite
        for position in ('prog.ail:3:9', 'prog.ail:15:5', 'prog.ail:19:5'):
            self.assertIn(position, text)
        self.assertEqual(text.count('construct:'), 3, text)
        self.assertEqual(text.count('why not typed:'), 3, text)
        self.assertEqual(text.count('write instead:'), 3, text)
        for code in ('yield i', 'top = max(d.items(), key=lambda kv: kv[1])', 'print(xs)'):
            self.assertIn(code, text)
        # the generator blocks gen, total and main: it comes first
        self.assertLess(text.index('prog.ail:3:9'), text.index('prog.ail:15:5'))
        self.assertLess(text.index('prog.ail:15:5'), text.index('prog.ail:19:5'))
        self.assertIn('(gen, total, main)', text)

    def test_s3_json_shape(self):
        result, _ = self.compile(THREE, extra=('--strict', '--json'))
        self.assertEqual(result.returncode, 3, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['schema'], 'ail.strict/1')
        self.assertEqual((report['status'], report['strict'], report['exit_code']), ('refused', True, 3))
        self.assertEqual(report['blocker_count'], 3)
        self.assertIsNone(report['incomplete'])
        blockers = report['blockers']
        self.assertEqual([b['rank'] for b in blockers], [1, 2, 3])
        for blocker in blockers:
            self.assertEqual(set(blocker), BLOCKER_KEYS)
            self.assertEqual(blocker['path'], 'prog.ail')
            self.assertIsInstance(blocker['line'], int)
            self.assertIsInstance(blocker['column'], int)
            for key in ('construct', 'why', 'write_instead', 'statement'):
                self.assertTrue(blocker[key] and isinstance(blocker[key], str), (key, blocker))
            self.assertIsInstance(blocker['blocks_lines'], int)
            self.assertIsInstance(blocker['blocks_functions'], list)
        self.assertEqual([b['line'] for b in blockers], [3, 15, 19])
        self.assertEqual([b['function'] for b in blockers], ['gen', 'best', 'show'])
        self.assertEqual(blockers[0]['blocks_functions'], ['gen', 'total', 'main'])
        self.assertGreaterEqual(blockers[0]['blocks_lines'], blockers[1]['blocks_lines'])
        self.assertIn('generators', blockers[0]['why'])
        self.assertIn('out.append', blockers[0]['write_instead'])

    def test_s5_no_general_alone_stops_at_the_first_refusal(self):
        result, exe = self.compile(THREE, AIL_NO_GENERAL='1')
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(exe.exists())
        self.assertNotIn('strict:', result.stderr)
        self.assertNotIn('typed-path blockers', result.stderr)
        self.assertEqual(result.stderr.count('not in the subset'), 1, result.stderr)

    def test_environment_variable_is_the_flag(self):
        result, _ = self.compile(THREE, AIL_STRICT='1')
        self.assertEqual(result.returncode, 3)
        self.assertTrue(result.stderr.startswith('strict: 3 typed-path blockers;'), result.stderr)
        off, _ = self.compile(THREE, AIL_STRICT='0')
        self.assertEqual(off.returncode, 0, off.stderr)

    def test_s7_refusal_without_a_position_is_located(self):
        result, _ = self.compile(NO_POSITION, extra=('--strict',))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(result.stderr.startswith('strict: 1 typed-path blocker;'), result.stderr)
        self.assertIn('prog.ail:4:9', result.stderr)
        self.assertIn('self.next = None', result.stderr)
        self.assertIn('write instead:', result.stderr)

    def test_s7_a_refusal_caused_by_an_earlier_one_is_not_listed(self):
        result, _ = self.compile(CONSEQUENCE, extra=('--strict', '--json'))
        report = json.loads(result.stdout)
        self.assertEqual(report['blocker_count'], 1, report)
        self.assertEqual(report['blockers'][0]['function'], 'gen')
        self.assertEqual(report['blockers'][0]['blocks_functions'], ['gen', 'total', 'main'])


class StrictBuilds(Base):
    def test_s2_typed_program_is_byte_identical_to_the_default_build(self):
        default, default_exe = self.compile(TYPED, name='plain')
        self.assertEqual((default.returncode, default.stderr), (0, ''))
        reference = default_exe.read_bytes()
        for label, extra, env in (('flag', ('--strict',), {}), ('env', (), {'AIL_STRICT': '1'}),
                                  ('no_general', (), {'AIL_NO_GENERAL': '1'})):
            result, exe = self.compile(TYPED, name='built_' + label, extra=extra, **env)
            self.assertEqual((result.returncode, result.stderr), (0, ''), label)
            self.assertEqual(exe.read_bytes(), reference, label)
        ran = subprocess.run([str(default_exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual((ran.returncode, ran.stdout), (0, '124\n'))

    def test_strict_with_json_reports_a_pass_like_the_default(self):
        result, exe = self.compile(TYPED, extra=('--strict', '--json'))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report['status'], report['exit_code']), ('passed', 0))
        self.assertTrue(exe.is_file())


class FallbackNote(Base):
    def test_s4_default_build_says_it_fell_back(self):
        result, exe = self.compile(OPTIONAL)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertRegex(lines[0], r'^note: prog\.ail:3:\d+: built on the general path \(about 20x slower\) because ')
        self.assertTrue(lines[0].endswith('; run with --strict to see why'), lines[0])
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, '3\n', ''))

    def test_s4_quiet_variable_silences_it(self):
        result, _ = self.compile(OPTIONAL, AIL_QUIET_FALLBACK='1')
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_s4_strict_refuses_what_the_default_falls_back_on(self):
        result, exe = self.compile(OPTIONAL, extra=('--strict', '--json'))
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(exe.exists())
        report = json.loads(result.stdout)
        self.assertEqual(report['blocker_count'], 1)
        self.assertEqual(report['blockers'][0]['line'], 3)
        self.assertIn('None', report['blockers'][0]['construct'])
        self.assertIn('sentinel', report['blockers'][0]['write_instead'])


class AilCommand(Base):
    """`ail build --strict` / `ail run --strict` through packaging/ail_lang (the SDK is this directory)."""

    def setUp(self):
        super().setUp()
        package = REPO / 'packaging' / 'ail_lang'
        if not package.is_dir():
            self.skipTest('no packaging/ beside AIL_CURRENT (an SDK export)')
        self.site = self.dir / 'site'
        shutil.copytree(package, self.site / 'ail_lang', ignore=shutil.ignore_patterns('__pycache__', 'sdk'))
        try:
            os.symlink(ROOT, self.site / 'ail_lang' / 'sdk', target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('cannot symlink the SDK directory here')
        if not (shutil.which('cc') or shutil.which('gcc') or shutil.which('clang') or os.environ.get('PIPE_CC')):
            self.skipTest('no C compiler')

    def ail(self, *args, **env):
        environment = self.env(PYTHONPATH=str(self.site), AIL_CACHE=str(self.dir / 'cache'), **env)
        return subprocess.run([sys.executable, '-B', '-m', 'ail_lang', *args], cwd=self.dir, capture_output=True,
                              text=True, timeout=900, env=environment)

    def test_s6_build_strict_lists_the_blockers(self):
        (self.dir / 'bad.py').write_text(THREE, encoding='utf-8')
        result = self.ail('build', '--strict', 'bad.py', '-o', 'bad')
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(result.stderr.startswith('strict: 3 typed-path blockers;'), result.stderr)
        self.assertIn('bad.py:3:9', result.stderr)
        self.assertFalse((self.dir / 'bad').exists())
        as_json = self.ail('build', '--strict', '--json', 'bad.py', '-o', 'bad')
        self.assertEqual(json.loads(as_json.stdout)['blocker_count'], 3)

    def test_s6_run_strict_runs_a_typed_program_and_refuses_a_fallback_one(self):
        (self.dir / 'good.py').write_text(TYPED, encoding='utf-8')
        good = self.ail('run', '--strict', 'good.py')
        self.assertEqual((good.returncode, good.stdout, good.stderr), (0, '124\n', ''))
        (self.dir / 'opt.py').write_text(OPTIONAL, encoding='utf-8')
        refused = self.ail('run', '--strict', 'opt.py')
        self.assertEqual(refused.returncode, 3, refused.stderr)
        self.assertIn('write instead:', refused.stderr)
        self.assertEqual(refused.stdout, '')
        fallback = self.ail('run', 'opt.py')
        self.assertEqual((fallback.returncode, fallback.stdout), (0, '3\n'))
        self.assertIn('run with --strict to see why', fallback.stderr)
        quiet = self.ail('run', 'opt.py', AIL_QUIET_FALLBACK='1')
        self.assertEqual((quiet.returncode, quiet.stderr), (0, ''))


if __name__ == '__main__':
    unittest.main()
