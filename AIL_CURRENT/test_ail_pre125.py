"""pre125: module-scope bare annotations on an attribute or subscript.

The accepted pre125 change proposed refusing `obj.attr: note()` / `xs[i]: note()` by name,
because the surface at that time evaluated neither the target nor the annotation. The current
tree contains the pre124 fix, which keeps CPython's order (target base and index expressions,
then the annotation) on both builds, so a refusal would regress it. This module re-applies
pre125's cases as CPython-parity regressions instead. A bare annotation on a plain name
(`count: int`) is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

CASES = {
    'attribute': r'''events = []


class Box:
    pass


box = Box()


def target():
    events.append("target")
    return box


def note():
    events.append("annotation")


target().value: note()
print(events)
''',
    'subscript': r'''events = []
values = [0, 0]


def index():
    events.append("index")
    return 1


def note():
    events.append("annotation")


values[index()]: note()
print(events, values)
''',
    'nested_attribute': r'''events = []


class Inner:
    pass


class Outer:
    def __init__(self):
        self.inner = Inner()


outer = Outer()


def note():
    events.append("annotation")


outer.inner.value: note()
print(events)
''',
    'negative_and_empty': r'''events = []
empty = []


def note():
    events.append("annotation")


empty[-1]: note()
print(events, empty)
''',
    'index_through_bindings': r'''events = []
rows = [[1, 2, 3]]
key = "k"
table = {"k": 2}


class Holder:
    def __init__(self):
        self.i = 0


holder = Holder()


def note():
    events.append("annotation")


rows[0][holder.i]: note()
rows[0][table[key]]: note()
print(events, rows)
''',
}

NAME_ANNOTATION = r'''count: int
print("ok")
'''


def _compile(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env), exe


def _run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', src.name], cwd=directory,
                          capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


class Pre125Tests(unittest.TestCase):
    def test_cpython_accepts_every_case(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre125-') as directory:
            for name, text in CASES.items():
                with self.subTest(case=name):
                    done = _run_cpython(directory, name, text)
                    self.assertEqual(done.returncode, 0, done.stderr)

    def test_both_builds_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre125-') as directory:
            for name, text in CASES.items():
                want = _run_cpython(directory, name, text)
                for general in (True, False):
                    with self.subTest(case=name, general=general):
                        done, exe = _compile(directory, '%s_%s' % (name, 'g' if general else 'd'),
                                             text, general)
                        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                        self.assertTrue(exe.exists())
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, 0, ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'),
                                         want.stdout.replace('\r\n', '\n'))

    def test_a_bare_annotation_on_a_name_is_still_accepted(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre125-') as directory:
            for general in (True, False):
                with self.subTest(general=general):
                    done, exe = _compile(directory, 'name_%s' % ('g' if general else 'd'),
                                         NAME_ANNOTATION, general)
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                         timeout=120)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, 'ok\n')


if __name__ == '__main__':
    unittest.main()
