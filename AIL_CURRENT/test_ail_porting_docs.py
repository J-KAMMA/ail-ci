"""docs/PORTING.md and its example files stay in sync, and every documented refusal is real.

Each entry in docs/PORTING.md shows a refusal message (`text` block), a `before` program that is
refused, and an `after` program that builds in the default mode and prints what CPython prints for
the `before` program. Every fenced ```python block follows an `<!-- example: NAME -->` marker
naming a file in AIL_CURRENT/language_examples/porting/ and must equal that file. The documented
message, with `prog.py` replaced by the real file name, must appear in the first stderr line of the
refused compile. Builds are skipped when no C compiler is available and run two at a time at most.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent / 'docs' / 'PORTING.md'
EXAMPLES = HERE / 'language_examples' / 'porting'
MARKED = re.compile(
    r'<!--\s*example:\s*(?P<name>[A-Za-z0-9_.-]+)\s*-->\n```python\n(?P<body>.*?)^```\n',
    re.M | re.S,
)
PYTHON_FENCE = re.compile(r'^```python\n', re.M)
TEXT_BLOCK = re.compile(r'^```text\n(?P<body>.*?)^```\n', re.M | re.S)
SECTION = re.compile(r'^## .*$', re.M)


def compiler():
    for name in ('cc', 'gcc', 'clang'):
        path = shutil.which(name)
        if path:
            return path
    return None


def documented_examples():
    text = DOC.read_text(encoding='utf-8')
    return text, [(match.group('name'), match.group('body')) for match in MARKED.finditer(text)]


def documented_entries():
    """Return (before name, after name, documented message) for every `##` entry."""
    text = DOC.read_text(encoding='utf-8')
    starts = [match.start() for match in SECTION.finditer(text)]
    bounds = list(zip(starts, starts[1:] + [len(text)]))
    sections = [text[start:end] for start, end in bounds]
    entries = []
    for section in sections:
        names = [match.group('name') for match in MARKED.finditer(section)]
        before = [name for name in names if name.endswith('_before.py')]
        after = [name for name in names if name.endswith('_after.py')]
        messages = TEXT_BLOCK.findall(section)
        if not before and not after:
            continue
        if len(before) != 1 or len(after) != 1 or len(messages) != 1:
            raise AssertionError('a section must have one text block and one before/after pair: %r'
                                 % (names,))
        entries.append((before[0], after[0], messages[0].strip('\n')))
    return entries


class PortingDocs(unittest.TestCase):
    def test_every_python_block_is_a_matching_example_file(self):
        text, examples = documented_examples()
        self.assertTrue(examples, 'docs/PORTING.md has no marked python examples')
        self.assertEqual(len(examples), len(PYTHON_FENCE.findall(text)),
                         'every ```python block needs an <!-- example: NAME --> marker')
        names = set()
        for name, body in examples:
            path = EXAMPLES / name
            self.assertTrue(path.is_file(), 'missing example file: %s' % path)
            self.assertEqual(body, path.read_text(encoding='utf-8'),
                             'docs/PORTING.md and %s differ' % path)
            names.add(name)
        self.assertEqual(names, {path.name for path in EXAMPLES.glob('*.py')},
                         'every file in %s must be shown in docs/PORTING.md' % EXAMPLES)

    def test_at_least_twelve_entries(self):
        entries = documented_entries()
        self.assertGreaterEqual(len(entries), 12,
                                'docs/PORTING.md documents only %d entries' % len(entries))

    def compile_entry(self, tmp, name):
        source = Path(tmp) / name
        shutil.copyfile(EXAMPLES / name, source)
        env = dict(os.environ, AIL_NO_CACHE='1')
        env.pop('AIL_NO_GENERAL', None)
        return subprocess.run(
            [sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
             '--syntax', 'python', name, '-o', 'program'],
            cwd=tmp, capture_output=True, text=True, timeout=600, env=env,
        )

    def test_before_files_are_refused_with_the_documented_message(self):
        if not compiler():
            self.skipTest('no C compiler')
        entries = documented_entries()

        def check(entry):
            before, _, message = entry
            with tempfile.TemporaryDirectory(prefix='ail-porting-') as tmp:
                built = self.compile_entry(tmp, before)
                first = (built.stderr or '').splitlines()[0] if (built.stderr or '').strip() else ''
                if built.returncode == 0:
                    return '%s built but is documented as refused' % before
                if not first:
                    return '%s was refused without a first stderr line' % before
                want = message.replace('prog.py', before)
                if want not in first:
                    return ('%s: documented message does not appear in the first stderr line\n'
                            'want: %s\ngot:  %s' % (before, want, first))
            return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            problems = [problem for problem in pool.map(check, entries) if problem]
        for problem in problems:
            self.fail(problem)

    def test_after_files_build_and_match_cpython(self):
        if not compiler():
            self.skipTest('no C compiler')
        entries = documented_entries()

        def check(entry):
            before, after, _ = entry
            with tempfile.TemporaryDirectory(prefix='ail-porting-') as tmp:
                want = subprocess.run([sys.executable, str(EXAMPLES / before)], cwd=tmp,
                                      capture_output=True,
                                      text=True, timeout=60, stdin=subprocess.DEVNULL,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                built = self.compile_entry(tmp, after)
                if built.returncode != 0:
                    return ('%s did not build:\n%s%s'
                            % (after, built.stdout[-1500:], built.stderr[-1500:]))
                got = subprocess.run([str(Path(tmp) / 'program')], cwd=tmp, capture_output=True,
                                     text=True, timeout=60, stdin=subprocess.DEVNULL)
                if got.returncode != want.returncode:
                    return ('%s exit code: CPython %s, AIL %s (stderr: %s)'
                            % (after, want.returncode, got.returncode, got.stderr[-1500:]))
                if got.stdout != want.stdout:
                    return ('%s stdout differs from CPython\nwant: %r\ngot:  %r'
                            % (after, want.stdout, got.stdout))
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            problems = [problem for problem in pool.map(check, entries) if problem]
        for problem in problems:
            self.fail(problem)


if __name__ == '__main__':
    unittest.main()
