"""docs/MIGRATING.md: every checklist item is a sample with a measured class (lane docmigr).

For each item the test

  * checks the fenced `python` block in docs/MIGRATING.md equals lab/migrating/<file> byte for byte;
  * reads the class from the row of that sample in lab/migrating/RESULTS.md;
  * runs the sample under CPython 3.12 and under a default-mode AIL build, then checks the class:
      same       stdout and exit status equal CPython's;
      loud stop  non-zero exit and the named error on the last line of stderr;
      refused    the build fails with the quoted text.

No C compiler, no test: the whole module is skipped.
"""
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
DOC = REPO / 'docs' / 'MIGRATING.md'
LAB = REPO / 'lab' / 'migrating'
RESULTS = LAB / 'RESULTS.md'

# (number, file, named error for loud stop, quoted build text for refused)
ITEMS = [
    (1, 'int64_overflow.py', 'OverflowError: integer overflow in +', None),
    (2, 'exact_int.py', 'OverflowError: integer overflow in *', None),
    (3, 'recursion.py', None, None),
    (4, 'eval.py', None, "the name 'eval' is not a known function/class/builtin"),
    (5, 'exec.py', None, 'exec() is not built'),
    (6, 'compile_builtin.py', None, "the name 'compile' is not a known function/class/builtin"),
    (7, 'dynamic_import.py', None, 'importlib.import_module'),
    (8, 'dunder_import.py', None, 'call to __import__()'),
    (9, 'catch_systemexit.py', None, 'a caught exception type SystemExit'),
    (10, 'bare_except_exit.py', None, 'a bare except: in a program that calls sys.exit()'),
    (11, 'complex_power.py', None, 'a negative number raised to a fractional power is a complex number'),
    (12, 'complex_literal.py', None, 'a constant of type complex'),
    (13, 'regex_group.py', 'ValueError: re: the group did not take part in the match', None),
    (14, 'negative_exponent.py', 'negative exponent on an integer', None),
    (15, 'open_mode.py', None, 'open() with a mode that is not a string literal'),
    (16, 'open_encoding.py', None, "open(encoding='utf-16'): only utf-8, ascii and latin-1 are built."),
    (17, 'uncaught_error.py', None, None),
    (18, 'threads.py', None, None),
    (19, 'no_pyc.py', None, 'py_compile.compile'),
    (20, 'stdlib_refusal.py', None, 'argparse.ArgumentParser'),
    (21, 'range_overflow.py', None, None),
]

SKIP_ENV = ('AIL_UNIFIED_FORCE', 'AIL_EXACT_INT', 'AIL_NO_GENERAL', 'AIL_UNIFIED', 'AIL_IR',
            'AIL_GENERAL', 'AIL_EXACT_INT')


def clean_env():
    env = dict(os.environ)
    for key in SKIP_ENV:
        env.pop(key, None)
    env['AIL_NO_CACHE'] = '1'
    return env


def code_blocks(text):
    return re.findall(r'```python\n(.*?)```', text, re.S)


def result_classes():
    """file name -> 'same' | 'loud stop' | 'refused', from the RESULTS.md table."""
    classes = {}
    for line in RESULTS.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3:
            continue
        m = re.fullmatch(r'`([^`]+\.py)`', cells[1])
        if not m:
            continue
        klass = cells[2]
        if 'loud stop' in klass:
            classes[m.group(1)] = 'loud stop'
        elif klass.startswith('refused'):
            classes[m.group(1)] = 'refused'
        elif klass.startswith('same'):
            classes[m.group(1)] = 'same'
    return classes


def have_c_compiler():
    return any(shutil.which(name) for name in ('cc', 'gcc', 'clang'))


def limit_memory():
    """Cap the address space of the child only (preexec_fn), never of this process."""
    if os.name != 'posix':
        return
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1500 * 1024 * 1024, 1500 * 1024 * 1024))
    except (ImportError, ValueError, OSError):
        pass


PREEXEC = limit_memory if os.name == 'posix' else None


class MigratingDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not have_c_compiler():
            raise unittest.SkipTest('no C compiler')
        cls.text = DOC.read_text(encoding='utf-8')
        cls.classes = result_classes()
        cls.tmp = tempfile.TemporaryDirectory()
        for _, name, _, _ in ITEMS:
            shutil.copyfile(LAB / name, Path(cls.tmp.name, name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_item_has_a_sample_and_a_class(self):
        self.assertEqual(len(ITEMS), len(code_blocks(self.text)))
        for number, name, _, _ in ITEMS:
            with self.subTest(item=number):
                self.assertTrue((LAB / name).is_file(), name)
                self.assertIn(name, self.classes, 'RESULTS.md has no class for ' + name)

    def test_code_blocks_equal_the_sample_files_byte_for_byte(self):
        blocks = code_blocks(self.text)
        for (number, name, _, _), block in zip(ITEMS, blocks):
            with self.subTest(item=number):
                self.assertEqual(block, (LAB / name).read_text(encoding='utf-8'), name)

    def build(self, name):
        source = Path(self.tmp.name, name)
        exe = Path(self.tmp.name, name[:-3] + '.bin')
        if exe.exists():
            exe.unlink()
        made = subprocess.run(
            [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
             '-o', exe.name],
            cwd=self.tmp.name, capture_output=True, text=True, timeout=600, env=clean_env(),
            preexec_fn=PREEXEC)
        return made, exe

    def run_python(self, name):
        return subprocess.run([sys.executable, str(Path(self.tmp.name, name))],
                              cwd=self.tmp.name, capture_output=True, text=True, timeout=120,
                              preexec_fn=PREEXEC)

    def test_every_sample_matches_its_class(self):
        for number, name, named_error, quoted in ITEMS:
            with self.subTest(item=number, sample=name):
                cpython = self.run_python(name)
                klass = self.classes[name]
                made, exe = self.build(name)
                if klass == 'refused':
                    self.assertNotEqual(made.returncode, 0,
                                        '%s built but RESULTS.md says refused' % name)
                    self.assertIn(quoted, made.stderr,
                                  '%s: refusal text missing\n' % name + made.stderr[-2000:])
                    continue
                self.assertEqual(made.returncode, 0,
                                 '%s did not build: %s' % (name, made.stderr[-2000:]))
                ran = subprocess.run([str(exe)], cwd=self.tmp.name, capture_output=True,
                                     text=True, timeout=180, preexec_fn=PREEXEC)
                if klass == 'same':
                    self.assertEqual(ran.returncode, cpython.returncode, name)
                    self.assertEqual(ran.stdout, cpython.stdout, name)
                elif klass == 'loud stop':
                    self.assertNotEqual(ran.returncode, 0, name + ' did not stop')
                    last = ran.stderr.strip().splitlines()[-1] if ran.stderr.strip() else ''
                    self.assertIn(named_error, last,
                                  '%s: named error not on stderr last line: %r' % (name, last))
                else:
                    self.fail('%s: unknown class %r' % (name, klass))


if __name__ == '__main__':
    unittest.main()
