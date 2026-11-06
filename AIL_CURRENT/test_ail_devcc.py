"""Opt-in `compile --cc=tcc|mir`: command mapping, named refusals, identical output.

The unit tests need no external tool.  The build tests skip when tcc is not installed; when it is,
they check five programs against gcc and check that one program using `__int128` is refused by name.
"""
import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
sys.path.insert(0, str(PKG))
SPEC = importlib.util.spec_from_file_location('devcc_under_test', PKG / 'devcc.py')
devcc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(devcc)

TCC = shutil.which('tcc')
TCC_VERSION = devcc.tcc_version(TCC) if TCC else None
TCC_SUPPORTED = TCC_VERSION is not None and TCC_VERSION >= devcc._TCC_MIN_VERSION
TCC_LABEL = '.'.join(str(part) for part in TCC_VERSION) if TCC_VERSION else 'unknown'
VERSION_REFUSAL = (r'^--cc=tcc: tcc %s cannot build this generated C; use tcc 0.9.28 '
                   r'or later, or build without --cc$' % re.escape(TCC_LABEL))

PROGRAMS = (
    'print(1 + 2 * 3)\n',
    'def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\nprint(fib(10))\n',
    'xs = [3, 1, 2]\nxs.sort()\nprint(xs)\n',
    'd = {"a": 1, "b": 2}\nprint(d["a"] + d["b"])\n',
    's = ""\nfor i in range(5):\n    s += str(i)\nprint(s)\n',
)


def fake_tool(directory, name='tcc'):
    path = Path(directory) / name
    path.write_text('#!/bin/sh\nexit 0\n')
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.saved = {key: os.environ.get(key) for key in ('AIL_DEVCC', 'PATH')}
        self.addCleanup(self.restore)

    def restore(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_off_by_default(self):
        os.environ.pop('AIL_DEVCC', None)
        self.assertIsNone(devcc.mode())
        command = ['cc', '-O2', '-o', 'out', 'in.c']
        self.assertIs(devcc.rewrite(command), command)

    def test_unknown_mode_refused(self):
        os.environ['AIL_DEVCC'] = 'zig'
        with self.assertRaises(devcc.DevCCRefusal):
            devcc.mode()

    def test_mir_is_refused_for_compile(self):
        os.environ['AIL_DEVCC'] = 'mir'
        with self.assertRaises(devcc.DevCCRefusal) as caught:
            devcc.rewrite(['cc', '-o', 'out', 'in.c'])
        self.assertIn('--cc=mir: c2m cannot write an executable', str(caught.exception))


class RewriteTests(unittest.TestCase):
    def setUp(self):
        self.saved = {key: os.environ.get(key) for key in ('AIL_DEVCC', 'PATH')}
        self.addCleanup(self.restore)
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-devcc-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tool = fake_tool(self.root)
        os.environ['PATH'] = str(self.root) + os.pathsep + os.environ.get('PATH', '')
        self.source = self.root / 'program.c'
        self.source.write_text('int main(void) { return 0; }\n')
        os.environ['AIL_DEVCC'] = 'tcc'

    def restore(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_maps_tool_and_drops_gcc_flags(self):
        command = ['/usr/bin/cc', '-O2', '-fno-tree-slp-vectorize', '-ffp-contract=off',
                   '-fopenmp-simd', '-Werror=implicit-int', '-fno-asynchronous-unwind-tables',
                   '-Wl,--gc-sections', '-DAIL_X=1', '-o', str(self.root / 'out'),
                   str(self.source), '-lm']
        prepared = devcc.rewrite(command)
        try:
            self.assertEqual(prepared[0], self.tool)
            self.assertNotIn('-O2', prepared)
            self.assertNotIn('-fno-tree-slp-vectorize', prepared)
            self.assertNotIn('-fno-asynchronous-unwind-tables', prepared)
            self.assertNotIn('-Wl,--gc-sections', prepared)
            self.assertIn('-DAIL_X=1', prepared)
            self.assertIn('-lm', prepared)
            moved = [part for part in prepared if part.endswith('.c')][0]
            self.assertNotEqual(moved, str(self.source))
            self.assertIn(devcc._PRELUDE_MARK, Path(moved).read_text())
            self.assertIn('int main(void)', Path(moved).read_text())
        finally:
            devcc.cleanup(prepared)
        self.assertFalse(Path(moved).exists())

    def test_int128_refused_by_name(self):
        self.source.write_text('int f(void) { __int128 x = 0; return (int)x; }\n')
        with self.assertRaises(devcc.DevCCRefusal) as caught:
            devcc.rewrite(['/usr/bin/cc', '-o', str(self.root / 'out'), str(self.source)])
        message = str(caught.exception)
        self.assertRegex(message, r'^--cc=tcc: this program uses __int128 \(line 1 of the generated C\), '
                                  r'which tcc does not build identically to gcc; build without --cc$')

    def test_other_tcc_constructs_refused_by_name(self):
        for text, construct in (
                ('unsigned __uint128_t f(void) { return 0; }\n', '__int128'),
                ('__int128_t f(void) { return 0; }\n', '__int128'),
                ('double f(double x) { return __builtin_fabs(x); }\n', '__builtin_fabs'),
                ('int f(double x) { return __builtin_isinf(x); }\n', '__builtin_isinf')):
            with self.subTest(construct=construct):
                self.source.write_text(text)
                with self.assertRaises(devcc.DevCCRefusal) as caught:
                    devcc.rewrite(['/usr/bin/cc', '-o', str(self.root / 'out'), str(self.source)])
                self.assertIn('this program uses %s (line 1 ' % construct,
                              str(caught.exception))

    def fake_version(self, version):
        tool = self.root / 'tcc'
        tool.write_text('#!/bin/sh\nif [ "$1" = "-v" ]; then '
                        'echo "tcc version %s (x86_64 Linux)"; fi\nexit 0\n' % version)
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
        return str(tool)

    def test_old_tcc_refused_by_version(self):
        self.fake_version('0.9.27')
        with self.assertRaises(devcc.DevCCRefusal) as caught:
            devcc.rewrite(['/usr/bin/cc', '-o', str(self.root / 'out'), str(self.source)])
        self.assertEqual(str(caught.exception),
                         '--cc=tcc: tcc 0.9.27 cannot build this generated C; use tcc 0.9.28 or '
                         'later, or build without --cc')

    def test_release_candidate_counts_as_its_version(self):
        tool = self.fake_version('0.9.28rc 2026-10-16 HEAD@e23dabed')
        self.assertEqual(devcc.tcc_version(tool), (0, 9, 28))
        prepared = devcc.rewrite(['/usr/bin/cc', '-o', str(self.root / 'out'), str(self.source)])
        try:
            self.assertEqual(prepared[0], tool)
        finally:
            devcc.cleanup(prepared)


class DefaultBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ail-devcc-default-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('AIL_')}
        self.env.update(AIL_SERVER='0', AIL_NO_CACHE='1', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')

    def compile(self, source, name, *flags):
        source_path = self.root / (name + '.py')
        source_path.write_text(source)
        output = self.root / name
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                 str(source_path), '--syntax', 'python', '-o', str(output), *flags],
                                capture_output=True, text=True, env=self.env, cwd=self.root, timeout=600)
        return result, output

    def test_no_flag_is_gcc_O2(self):
        debug = self.root / 'debug'
        build, _ = self.compile(PROGRAMS[0], 'default_debug', '--debug-dir', str(debug))
        self.assertEqual(build.returncode, 0, build.stderr)
        import json
        report = json.loads((debug / 'native_report.json').read_text())
        commands = [' '.join(op['command']) for op in report['operations']]
        self.assertTrue(any('-O2' in command for command in commands), commands)
        self.assertFalse(any('tcc' in command for command in commands), commands)


@unittest.skipUnless(TCC, 'tcc is not installed')
class BuildTests(DefaultBuildTests):
    def run_program(self, output):
        return subprocess.run([str(output)], capture_output=True, text=True, timeout=120)

    def test_real_tcc_is_supported_or_refused_by_version(self):
        """The tcc on PATH either builds correctly or is refused by its `tcc -v` name."""
        build, output = self.compile(PROGRAMS[0], 'real_tcc', '--cc=tcc')
        if TCC_SUPPORTED:
            self.assertEqual(build.returncode, 0, build.stderr)
            gcc_build, gcc_out = self.compile(PROGRAMS[0], 'real_tcc_gcc')
            self.assertEqual(gcc_build.returncode, 0, gcc_build.stderr)
            gcc_run, tcc_run = self.run_program(gcc_out), self.run_program(output)
            self.assertEqual((gcc_run.stdout, gcc_run.stderr, gcc_run.returncode),
                             (tcc_run.stdout, tcc_run.stderr, tcc_run.returncode))
        else:
            self.assertNotEqual(build.returncode, 0)
            self.assertRegex(build.stderr, VERSION_REFUSAL)

    @unittest.skipUnless(TCC_SUPPORTED, 'tcc 0.9.28 or later is not installed')
    def test_five_programs_match_gcc(self):
        for index, source in enumerate(PROGRAMS):
            with self.subTest(index=index):
                gcc_build, gcc_out = self.compile(source, 'g%d' % index)
                self.assertEqual(gcc_build.returncode, 0, gcc_build.stderr)
                tcc_build, tcc_out = self.compile(source, 't%d' % index, '--cc=tcc')
                self.assertEqual(tcc_build.returncode, 0, tcc_build.stderr)
                gcc_run, tcc_run = self.run_program(gcc_out), self.run_program(tcc_out)
                self.assertEqual((gcc_run.stdout, gcc_run.stderr, gcc_run.returncode),
                                 (tcc_run.stdout, tcc_run.stderr, tcc_run.returncode))

    @unittest.skipUnless(TCC_SUPPORTED, 'tcc 0.9.28 or later is not installed')
    def test_int128_program_is_refused(self):
        build, _ = self.compile('print(list(range(0, 10, 3)))\n', 'refused', '--cc=tcc')
        self.assertNotEqual(build.returncode, 0)
        self.assertRegex(build.stderr, r'--cc=tcc: this program uses __int128 '
                                       r'\(line \d+ of the generated C\), which tcc does not '
                                       r'build identically to gcc; build without --cc')


if __name__ == '__main__':
    unittest.main()
