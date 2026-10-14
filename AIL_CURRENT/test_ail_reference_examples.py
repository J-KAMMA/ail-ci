"""Every example in AIL_REFERENCE.md (the core) and AIL_REFERENCE_MORE.md compiles and behaves
as the documents say.

- A ```ail block containing `fn main` is compiled with `ail_chatgpt.py compile` and run in a
  fresh directory. It must exit 0 unless its first lines declare `# exit: N`; `# args: a b`
  passes command-line arguments. A ```text block directly after it is the exact stdout.
- A ```ail-refused block holds one or more programs separated by blank lines; each must FAIL to
  compile (they show what the compiler rejects).
- ```ail blocks without `fn main` are fragments and are not compiled.
- Every session reads the core in full, so its size is capped. Its last line is a line-number
  index of AIL_REFERENCE_MORE.md (each `## ` section's name before any `:` and its line range), so
  a session reads one slice with `sed -n A,Bp`; the test recomputes it, and
  `python3 tools/ref_index.py` (from the repository root) rewrites it after MORE changes.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = HERE / 'AIL_REFERENCE.md'
MORE = HERE / 'AIL_REFERENCE_MORE.md'
CORE_MAX_CHARS = 3500
INDEX_PREFIX = 'MORE (`sed -n A,Bp AIL_REFERENCE_MORE.md`): '
FENCE = re.compile(r'^```([\w-]*)\n(.*?)^```\n', re.M | re.S)


def blocks():
    result = []
    for doc in (CORE, MORE):
        result.extend(doc_blocks(doc))
    return result


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


def more_index(text=None):
    """The core's last line: each `## ` section of MORE as `Name A-B`, A the heading line and B
    the section's last non-blank line."""
    if text is None:
        text = MORE.read_text(encoding='utf-8')
    lines = text.split('\n')
    heads = []
    fenced = False
    for number, row in enumerate(lines, 1):
        if row.startswith('```'):
            fenced = not fenced
        elif not fenced and row.startswith('## '):
            heads.append((number, row[3:].split(':', 1)[0].strip()))
    parts = []
    for k, (start, name) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        while end > start and not lines[end - 1].strip():
            end -= 1
        parts.append('%s %d-%d' % (name, start, end))
    return INDEX_PREFIX + ', '.join(parts) + '.'


def header(body, key):
    for row in body.splitlines()[:3]:
        if row.startswith('# %s:' % key):
            return row.split(':', 1)[1].split()
    return None


class ReferenceExamples(unittest.TestCase):
    def compile(self, body, root, name):
        src = root / (name + '.ail')
        src.write_text(body, encoding='utf-8')
        exe = root / name
        proc = subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                               str(src), '-o', str(exe)], cwd=HERE, capture_output=True,
                              text=True, timeout=300)
        return proc, exe

    def test_core_size_and_pointer(self):
        core = CORE.read_text(encoding='utf-8')
        self.assertLessEqual(len(core), CORE_MAX_CHARS, 'move detail to %s' % MORE.name)
        self.assertTrue(any(lang == 'ail' and 'fn main' in body for lang, body, _, _ in doc_blocks(CORE)))
        last = core.rstrip('\n').rsplit('\n', 1)[1]
        self.assertEqual(last, more_index(), 'stale MORE index: run python3 tools/ref_index.py')

    def test_index_names_are_unique(self):
        names = [part.rsplit(' ', 1)[0] for part in more_index()[len(INDEX_PREFIX):-1].split(', ')]
        self.assertEqual(len(names), len(set(names)), names)
        self.assertTrue(all(',' not in n for n in names), names)

    def test_runnable_examples(self):
        runnable = [b for b in blocks() if b[0] == 'ail' and 'fn main' in b[1]]
        self.assertGreaterEqual(len(runnable), 4)
        for lang, body, line, expected in runnable:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                proc, exe = self.compile(body, root, 'example')
                self.assertEqual(proc.returncode, 0, '%s did not compile:\n%s%s'
                                 % (line, proc.stdout[-1500:], proc.stderr[-1500:]))
                args = header(body, 'args') or []
                want_exit = int((header(body, 'exit') or ['0'])[0])
                run = subprocess.run([str(exe)] + args, cwd=root, capture_output=True,
                                     text=True, timeout=60, input='')
                self.assertEqual(run.returncode, want_exit, '%s exit %d, stderr: %s'
                                 % (line, run.returncode, run.stderr[-800:]))
                if expected is not None:
                    self.assertEqual(run.stdout, expected, '%s stdout' % line)

    def test_refused_examples(self):
        # One ```ail-refused block may hold several programs separated by blank lines.
        programs = []
        for lang, body, line, expected in blocks():
            if lang == 'ail-refused':
                for offset, program in enumerate(re.split(r'\n\s*\n', body)):
                    if program.strip():
                        programs.append((line, program + '\n'))
        self.assertGreater(len(programs), 5)
        for line, program in programs:
            with self.subTest(line=line, program=program[:60]), tempfile.TemporaryDirectory() as tmp:
                proc, exe = self.compile(program, Path(tmp), 'refused')
                self.assertNotEqual(proc.returncode, 0, 'documented as refused but compiled '
                                    '(block at %s):\n%s' % (line, program))
                self.assertNotIn('Traceback', proc.stdout + proc.stderr,
                                 'compiler crashed instead of refusing:\n%s' % program)


if __name__ == '__main__':
    unittest.main()
