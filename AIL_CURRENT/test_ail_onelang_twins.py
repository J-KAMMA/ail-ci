"""Every ``language_examples`` source keeps a checked-in Python twin.

The twin is regenerated from the ``.ail`` text and must equal the file byte for byte; ten fixed
twins are also built both ways (brace source and converted Python) and the generated C must be
identical, or differ only by the module prefix the Python merge adds (``m__f`` for ``use m``).
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
EXAMPLES = ROOT / 'language_examples'
CLI = ROOT / 'ail_chatgpt.py'
TOOL = REPO / 'tools' / 'ail2py.py'
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None

_spec = importlib.util.spec_from_file_location('ail2py_tool', TOOL)
ail2py = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ail2py)

FIXED_TWINS = (
    'binary_copy',
    'block_line_count',
    'block_line_count_for',
    'block_line_stats',
    'block_line_stats_for',
    'mixed_output_main',
    'row_reduce_main',
    'utf8_roundtrip',
    'block_use_math',
    'codepoint_checksum',
)

USE = re.compile(r'^\s*use\s+([A-Za-z_]\w*)\s*;', re.M)


def twin_text(source):
    text = source.read_text(encoding='utf-8')
    body = ail2py.convert(text) if ail2py.ail_syntax.detect(text) else text
    if not body.endswith('\n'):
        body += '\n'
    return ail2py.twin_header(source) + '\n' + body


def local_modules(stem, seen=None):
    """The brace modules ``stem`` uses, transitively."""
    seen = set() if seen is None else seen
    source = EXAMPLES / (stem + '.ail')
    text = source.read_text(encoding='utf-8')
    if not ail2py.ail_syntax.detect(text):
        return []
    found = []
    for name in USE.findall(text):
        if name in seen:
            continue
        module = EXAMPLES / (name + '.ail')
        if module.is_file() and ail2py.ail_syntax.detect(module.read_text(encoding='utf-8')):
            seen.add(name)
            found.append(name)
            found.extend(local_modules(name, seen))
    return found


def run(command):
    env = dict(os.environ, AIL_NO_CACHE='1')
    return subprocess.run(command, capture_output=True, timeout=1800, env=env)


class TwinTextTests(unittest.TestCase):
    def test_every_ail_has_a_twin_that_reconverts(self):
        sources = sorted(EXAMPLES.rglob('*.ail'))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source.name):
                target = source.with_suffix('.py')
                self.assertTrue(target.is_file(), f'missing twin {target.name}')
                self.assertEqual(target.read_text(encoding='utf-8'), twin_text(source))

    def test_twin_count_equals_ail_count(self):
        twins = [path for path in EXAMPLES.rglob('*.py')
                 if ail2py._is_twin(path.read_text(encoding='utf-8'))]
        self.assertEqual(len(twins), len(list(EXAMPLES.rglob('*.ail'))))

    def test_a_foreign_py_file_is_left_alone(self):
        with tempfile.TemporaryDirectory(prefix='ail-twins-skip-') as directory:
            work = Path(directory)
            (work / 'thing.ail').write_text('def f():\n    return 1\n', encoding='utf-8')
            foreign = work / 'thing.py'
            foreign.write_text('# hand written\n', encoding='utf-8')
            done = run([sys.executable, '-B', str(TOOL), '--twins', str(work)])
            self.assertEqual(done.returncode, 0, done.stderr[-3000:])
            self.assertEqual(foreign.read_text(encoding='utf-8'), '# hand written\n')
            self.assertIn(b'thing.py', done.stderr)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TwinBuildTests(unittest.TestCase):
    def test_python_source_wins_over_its_generated_twin(self):
        with tempfile.TemporaryDirectory(prefix='ail-twins-import-') as directory:
            temp = Path(directory)
            outputs = {}
            for label, include_twin in (('twin', True), ('source', False)):
                work = temp / label
                work.mkdir()
                shutil.copyfile(EXAMPLES / 'integer_series.ail', work / 'integer_series.ail')
                if include_twin:
                    shutil.copyfile(EXAMPLES / 'integer_series.py', work / 'integer_series.py')
                entry = work / 'entry.py'
                entry.write_text('from integer_series import above\nprint(above([3, 1, 2], 2))\n',
                                 encoding='utf-8')
                built = run([sys.executable, '-B', str(CLI), 'compile', str(entry),
                             '--syntax', 'python', '-o', str(work / 'program'), '--strict',
                             '--debug-dir', str(work / 'debug')])
                self.assertEqual(built.returncode, 0, built.stderr[-3000:])
                outputs[label] = (work / 'debug' / 'program.c').read_text(encoding='utf-8')
                ran = subprocess.run([str(work / 'program')], capture_output=True, text=True)
                self.assertEqual(ran.returncode, 0, ran.stderr[-3000:])
                self.assertEqual(ran.stdout, '[2, 3]\n')
            self.assertEqual(outputs['twin'], outputs['source'])

    def test_ten_fixed_twins_build_to_the_same_c(self):
        with tempfile.TemporaryDirectory(prefix='ail-twins-build-') as directory:
            temp = Path(directory)
            for stem in FIXED_TWINS:
                with self.subTest(stem):
                    modules = local_modules(stem)
                    work = temp / stem
                    work.mkdir()
                    for name in [stem, *modules]:
                        shutil.copyfile(EXAMPLES / (name + '.py'), work / (name + '.py'))
                    original = run([sys.executable, '-B', str(CLI), 'compile',
                                    str(EXAMPLES / (stem + '.ail')), '-o', str(work / 'original.bin'),
                                    '--strict', '--debug-dir', str(work / 'original-debug')])
                    self.assertEqual(original.returncode, 0, original.stderr[-3000:])
                    twin = run([sys.executable, '-B', str(CLI), 'compile', str(work / (stem + '.py')),
                                '--syntax', 'python', '-o', str(work / 'twin.bin'),
                                '--strict', '--debug-dir', str(work / 'twin-debug')])
                    self.assertEqual(twin.returncode, 0, twin.stderr[-3000:])
                    left = (work / 'original-debug' / 'program.c').read_text(encoding='utf-8')
                    right = (work / 'twin-debug' / 'program.c').read_text(encoding='utf-8')
                    if left == right:
                        result = 'identical'
                    else:
                        renamed = right
                        for name in modules:
                            renamed = renamed.replace(name + '__', '')
                        result = 'identical-renamed' if left == renamed else 'differ'
                    self.assertIn(result, ('identical', 'identical-renamed'),
                                  'generated C differs beyond module renames')


if __name__ == '__main__':
    unittest.main()
