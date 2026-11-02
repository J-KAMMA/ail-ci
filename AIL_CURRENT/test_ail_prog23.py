"""Typed reach for eight real programs, and the compiler blockers fixed for two of them.

The typed path already accepted g02_026, g18_030, t102 and t069.  t115 and t143 are now typed:

* t115 binds a tuple target from matching tuple/list expressions
  (`first, second = words[:mid], words[mid:]`), which `iterlower.known_sequences` used to mark
  unknown, so the later `for a, b in zip(first, second)` was refused.
* t143 needs a conditional producing numeric lists and unannotated set operators (`a & b`,
  `a | b`, `a - b`, `a ^ b`) to stay sets through assignment.  A str/bytes-keyed unannotated set
  keeps its keys in ail_stab/ail_btab, so the int-table set-operator path deliberately leaves it
  to the general path (compared below, not built with --strict).

g15_004 and g25_026 keep their recorded follow-ups (exception chaining/scalar Optional/conditional
class values, and generated Enum dunders/module-level tables).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None

PROGRAMS = (
    ('g02_026', 'lab/census/programs/gdev/g02_026.py', None),
    ('g15_004', 'lab/census/programs/gdev/g15_004.py', None),
    ('g25_026', 'lab/census/programs/gdev/g25_026.py', None),
    ('g18_030', 'lab/census/programs/gdev/g18_030.py', None),
    ('t102', 'lab/census/programs/dev/t102.py', 'lab/corpus/tasks/t102'),
    ('t069', 'lab/corpus/programs/glm-5.3-flash-free/t069.py', 'lab/corpus/tasks/t069'),
    ('t115', 'lab/corpus/programs/deepseek-v4.1-flash-free/t115.py', 'lab/corpus/tasks/t115'),
    ('t143', 'lab/corpus/programs/deepseek-v4.1-flash-free/t143.py', 'lab/corpus/tasks/t143'),
)
NEWLY_TYPED = ('t115', 't143')
GENERAL_FAILS = ('g15_004',)

TUPLE_LIST_BINDINGS = '''
def halves(words: list[str]) -> None:
    mid = len(words) // 2
    first, second = words[:mid], words[mid:]
    out = []
    for a, b in zip(first, second):
        out.append(a + b)
    print(out)


def literals() -> None:
    a, b = [1, 2], [3, 4]
    print(a[0] + b[1])
    c, d = (5, 6), (7, 8)
    print(c[0] + d[1])


def run() -> None:
    halves(["a", "b", "c", "d"])
    literals()


run()
'''

SET_OPERATORS = '''
def run() -> None:
    a = set([1, 2, 3, 4])
    b = set([3, 4, 5])
    c = b
    common = a & c
    union = a | c
    left = a - c
    right = a ^ c
    print(sorted(common))
    print(sorted(union))
    print(sorted(left))
    print(sorted(right))
    print(len(common), len(union), len(left), len(right))


run()
'''

STR_SET_OPERATORS = '''
def run() -> None:
    a = set(["a", "b"])
    b = set(["b", "c"])
    common = a & b
    union = a | b
    left = a - b
    right = a ^ b
    print(sorted(common), sorted(union), sorted(left), sorted(right))


run()
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, env=env, timeout=600)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach23(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-prog23-')
        self.env = dict(os.environ, AIL_NO_CACHE='1')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, src, name, strict=False):
        out = Path(self.tmp) / (name + ('.strict' if strict else ''))
        cmd = [sys.executable, '-B', CLI, 'compile']
        if strict:
            cmd.append('--strict')
        cmd += [str(src), '--syntax', 'python', '-o', str(out)]
        return run(cmd, Path(self.tmp), env=self.env), out

    def cases(self, task_dir):
        if task_dir is None:
            return [b'']
        base = REPO / task_dir
        return [(base / ('in%d.txt' % i)).read_bytes() for i in range(3)]

    def compare(self, src, exe, task_dir):
        for stdin in self.cases(task_dir):
            want = run([sys.executable, str(src)], Path(self.tmp), stdin=stdin)
            got = run([str(exe)], Path(self.tmp), stdin=stdin)
            self.assertEqual(got.returncode, want.returncode, stdin[:200])
            self.assertEqual(got.stdout, want.stdout, stdin[:200])

    def build_probe(self, text, name):
        src = Path(self.tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        built, exe = self.build(src, name, strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_buildable_programs_match_cpython(self):
        for name, rel, task in PROGRAMS:
            if name in GENERAL_FAILS:
                continue
            src = REPO / rel
            built, exe = self.build(src, name)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_newly_typed_build_strict(self):
        for name, rel, task in PROGRAMS:
            if name not in NEWLY_TYPED:
                continue
            src = REPO / rel
            built, exe = self.build(src, name, strict=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_tuple_list_target_bindings(self):
        self.build_probe(TUPLE_LIST_BINDINGS, 'tuple_list_bindings')

    def test_unannotated_set_operators(self):
        self.build_probe(SET_OPERATORS, 'set_operators')

    def test_str_set_operators_stay_on_the_general_path(self):
        src = Path(self.tmp) / 'str_set_operators.py'
        src.write_text(STR_SET_OPERATORS, encoding='utf-8')
        built, exe = self.build(src, 'str_set_operators')
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_follow_ups_keep_exact_first_reasons(self):
        g15 = self.build(REPO / 'lab/census/programs/gdev/g15_004.py', 'g15_004', strict=True)
        output = (g15[0].stdout + g15[0].stderr).decode('utf-8', 'replace')
        self.assertNotEqual(g15[0].returncode, 0, output[-3000:])
        self.assertIn('raise ... from ...', output)

        g25 = self.build(REPO / 'lab/census/programs/gdev/g25_026.py', 'g25_026', strict=True)
        output = (g25[0].stdout + g25[0].stderr).decode('utf-8', 'replace')
        self.assertNotEqual(g25[0].returncode, 0, output[-3000:])
        self.assertIn('dunder method _AilIntEnum.__lt__', output)


if __name__ == '__main__':
    unittest.main()
