"""docs/QUICKSTART.md and its example files stay in sync, compile, and print what CPython prints.

Every fenced ```python block in docs/QUICKSTART.md must follow an `<!-- example: NAME -->`
marker naming a file in AIL_CURRENT/language_examples/quickstart/. The block text must equal that
file exactly, and the file must compile with `ail_chatgpt.py compile --syntax python` and print
the same stdout and exit code as CPython.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent / 'docs' / 'QUICKSTART.md'
EXAMPLES = HERE / 'language_examples' / 'quickstart'
MARKED = re.compile(
    r'<!--\s*example:\s*(?P<name>[A-Za-z0-9_.-]+)\s*-->\n```python\n(?P<body>.*?)^```\n',
    re.M | re.S,
)
PYTHON_FENCE = re.compile(r'^```python\n', re.M)


def documented_examples():
    text = DOC.read_text(encoding='utf-8')
    return text, [(match.group('name'), match.group('body')) for match in MARKED.finditer(text)]


class QuickstartDocs(unittest.TestCase):
    def test_every_python_block_is_a_matching_example_file(self):
        text, examples = documented_examples()
        self.assertTrue(examples, 'docs/QUICKSTART.md has no marked python examples')
        self.assertEqual(len(examples), len(PYTHON_FENCE.findall(text)),
                         'every ```python block needs an <!-- example: NAME --> marker')
        names = set()
        for name, body in examples:
            path = EXAMPLES / name
            self.assertTrue(path.is_file(), 'missing example file: %s' % path)
            self.assertEqual(body, path.read_text(encoding='utf-8'),
                             'docs/QUICKSTART.md and %s differ' % path)
            names.add(name)
        self.assertEqual(names, {path.name for path in EXAMPLES.glob('*.py')},
                         'every file in %s must be shown in docs/QUICKSTART.md' % EXAMPLES)

    def test_examples_compile_and_match_cpython(self):
        _, examples = documented_examples()
        build_env = dict(os.environ, AIL_NO_CACHE='1')
        build_env.pop('AIL_NO_GENERAL', None)
        for name, _ in examples:
            with self.subTest(example=name), tempfile.TemporaryDirectory(prefix='ail-quickstart-') as tmp:
                source = EXAMPLES / name
                exe = Path(tmp) / 'program'
                want = subprocess.run([sys.executable, str(source)], cwd=tmp, capture_output=True,
                                      text=True, timeout=60,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                self.assertEqual(want.returncode, 0, '%s under CPython:\n%s' % (name, want.stderr[-1500:]))
                built = subprocess.run(
                    [sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                     '--syntax', 'python', str(source), '-o', str(exe)],
                    cwd=tmp, capture_output=True, text=True, timeout=300, env=build_env,
                )
                self.assertEqual(built.returncode, 0, '%s did not compile:\n%s%s'
                                 % (name, built.stdout[-1500:], built.stderr[-1500:]))
                got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, text=True, timeout=60)
                self.assertEqual(got.returncode, want.returncode, '%s exit code, stderr: %s'
                                 % (name, got.stderr[-1500:]))
                self.assertEqual(got.stdout, want.stdout, '%s stdout differs from CPython' % name)
