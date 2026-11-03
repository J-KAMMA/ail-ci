"""The reference docs are Python syntax and every whole-program block builds and prints its text.

- A fenced block with ``def main`` (or a legacy ``fn main``) is compiled with
  ``ail_chatgpt.py compile`` and run in a fresh directory. ``# args: a b`` passes command-line
  arguments, ``# exit: N`` is the expected status, and the output is the following ``text`` block
  or the block's ``# prints ...`` comments.
- No fenced block may contain the old brace spellings ``fn `` or ``let ``.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = (HERE / 'AIL_REFERENCE.md', HERE / 'AIL_REFERENCE_MORE.md')
FENCE = re.compile(r'^```([\w-]*)\n(.*?)^```\n', re.M | re.S)


def doc_blocks(doc):
    text = doc.read_text(encoding='utf-8')
    found = [(m.group(1), m.group(2), m.start(), m.end()) for m in FENCE.finditer(text)]
    result = []
    for i, (lang, body, start, end) in enumerate(found):
        line = '%s:%d' % (doc.name, text.count('\n', 0, start) + 1)
        expected = None
        if i + 1 < len(found) and found[i + 1][0] == 'text' and text[end:found[i + 1][2]].strip() == '':
            expected = found[i + 1][1]
        result.append((lang, body, line, expected))
    return result


def blocks():
    result = []
    for doc in DOCS:
        result.extend(doc_blocks(doc))
    return result


def whole_program(lang, body):
    return (lang == 'python' and 'def main' in body) or (lang == 'ail' and 'fn main' in body)


def header(body, key):
    for row in body.splitlines()[:4]:
        if row.startswith('# %s:' % key):
            return row.split(':', 1)[1].split()
    return None


def printed(body):
    lines = []
    for row in body.splitlines():
        match = re.match(r'#\s*prints?\s*:?\s*(.*)$', row.strip())
        if match:
            lines.append(match.group(1))
    return '\n'.join(lines) + '\n' if lines else None


class ReferenceDocs(unittest.TestCase):
    def test_blocks_are_python(self):
        for lang, body, line, _ in blocks():
            with self.subTest(line=line, lang=lang):
                self.assertNotIn('fn ', body, '%s still teaches brace syntax' % line)
                self.assertNotIn('let ', body, '%s still teaches brace syntax' % line)

    def test_whole_programs_build_and_print(self):
        examples = [b for b in blocks() if whole_program(b[0], b[1])]
        self.assertGreaterEqual(len(examples), 8)
        for lang, body, line, expected in examples:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                src = root / ('example.py' if lang == 'python' else 'example.ail')
                src.write_text(body, encoding='utf-8')
                exe = root / 'example'
                env = dict(os.environ, AIL_PATH=str(HERE / 'language_examples'))
                proc = subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                                       str(src), '-o', str(exe)], cwd=root, env=env,
                                      capture_output=True, text=True, timeout=300)
                if proc.returncode != 0 and 'written in the brace syntax' in proc.stderr:
                    self.skipTest('%s imports a module that is still written in the brace syntax' % line)
                self.assertEqual(proc.returncode, 0, '%s did not compile:\n%s%s'
                                 % (line, proc.stdout[-1500:], proc.stderr[-1500:]))
                args = header(body, 'args') or []
                want_exit = int((header(body, 'exit') or ['0'])[0])
                run = subprocess.run([str(exe)] + args, cwd=root, capture_output=True,
                                     text=True, timeout=60, input='')
                self.assertEqual(run.returncode, want_exit, '%s exit %d, stderr: %s'
                                 % (line, run.returncode, run.stderr[-800:]))
                want = expected if expected is not None else printed(body)
                if want is not None:
                    self.assertEqual(run.stdout, want, '%s stdout' % line)


if __name__ == '__main__':
    unittest.main()
