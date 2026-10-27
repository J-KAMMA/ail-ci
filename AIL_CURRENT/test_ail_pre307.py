"""Pre-307: deleting a list element outside its bounds names CPython's assignment message.

The rbrbpre19 review recorded ``del a[-9223372036854775808]``: both builds exited 1 with
matching stdout, but stderr said ``IndexError: list index out of range`` (the typed path said
``pop index out of range``) where CPython says ``IndexError: list assignment index out of
range``.  List deletion now uses the assignment wording on both paths, while ``.pop()`` keeps
its own ``pop index out of range`` / ``pop from empty list`` messages.  The cases below cover
an ordinary index, negative and int64-boundary indices, the empty list, float and str lists,
an exception caught without reading its text, and one read through ``str(e)``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
ASSIGN = 'IndexError: list assignment index out of range'
ASSIGN_BARE = 'list assignment index out of range'

UNCAUGHT = {
    'ordinary': 'a = [1, 2, 3]\nprint("before")\ndel a[3]\n',
    'negative': 'a = [1, 2, 3]\nprint("before")\ndel a[-4]\n',
    'int64_min': 'a = [1, 2, 3]\nprint("before")\ndel a[-9223372036854775808]\n',
    'int64_max': 'a = [1, 2, 3]\nprint("before")\ndel a[9223372036854775807]\n',
    'empty': 'a = []\nprint("before")\ndel a[0]\n',
    'float_list': 'a = [1.0, 2.0]\nprint("before")\ndel a[5]\n',
    'str_list': 'a = ["x", "y"]\nprint("before")\ndel a[5]\n',
}
POP = {
    'pop_index': 'a = [1, 2, 3]\nprint("before")\na.pop(5)\n',
    'pop_empty': 'a = []\nprint("before")\na.pop()\n',
}
CAUGHT = {
    'plain': '''def main():
    a = [1, 2, 3]
    try:
        del a[5]
    except IndexError:
        print("caught")
    print("after")


main()
''',
    'text': '''def main():
    a = [1, 2, 3]
    try:
        del a[5]
    except IndexError as e:
        print("caught", type(e).__name__, str(e))
    print("after")


main()
''',
}


def _build(directory, name, source, general):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=300, env=env)
    return built, exe


def _run(directory, name, source, general):
    built, exe = _build(directory, name, source, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-4000:]
    done = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (done.stdout.replace(b'\r\n', b'\n'), done.returncode,
            done.stderr.replace(b'\r\n', b'\n')), ''


def _last_line(stderr):
    lines = [line for line in stderr.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre307Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre307-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_out_of_range_delete_names_assignment_message(self):
        for name, source in UNCAUGHT.items():
            ref = Path(self.dir, name + '_cpython.py')
            ref.write_text(source, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(ref)], capture_output=True, timeout=60)
            self.assertEqual(want.returncode, 1, name)
            self.assertEqual(_last_line(want.stderr), ASSIGN, name)
            for general in (False, True):
                got, error = _run(self.dir, name, source, general)
                where = '%s %s' % (name, 'general' if general else 'default')
                self.assertIsNotNone(got, where + ' build failed:\n' + error)
                self.assertEqual(got[0], want.stdout, where)
                self.assertEqual(got[1], want.returncode, where)
                last = _last_line(got[2])
                # The typed path's uncaught traps print only their text (no ``IndexError:``
                # prefix), a pre-existing difference recorded in DEVLOG; both paths must
                # carry the assignment wording instead of the old index/pop wording.
                self.assertIn(last, (ASSIGN, ASSIGN_BARE), where + ' stderr:\n' + got[2].decode('utf-8', 'replace'))

    def test_pop_keeps_its_own_message(self):
        for name, source in POP.items():
            ref = Path(self.dir, name + '_cpython.py')
            ref.write_text(source, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(ref)], capture_output=True, timeout=60)
            for general in (False, True):
                got, error = _run(self.dir, name, source, general)
                where = '%s %s' % (name, 'general' if general else 'default')
                self.assertIsNotNone(got, where + ' build failed:\n' + error)
                self.assertEqual(got[0], want.stdout, where)
                self.assertEqual(got[1], want.returncode, where)
                expected = _last_line(want.stderr)
                self.assertIn(_last_line(got[2]), (expected, expected.split(': ', 1)[1]), where)

    def test_caught_delete_matches_cpython(self):
        for name, source in CAUGHT.items():
            ref = Path(self.dir, name + '_cpython.py')
            ref.write_text(source, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(ref)], capture_output=True, timeout=60)
            self.assertEqual(want.returncode, 0, name)
            for general in (False, True):
                got, error = _run(self.dir, name, source, general)
                where = '%s %s' % (name, 'general' if general else 'default')
                self.assertIsNotNone(got, where + ' build failed:\n' + error)
                self.assertEqual(got[0], want.stdout, where)
                self.assertEqual(got[1], want.returncode, where)


if __name__ == '__main__':
    unittest.main()
