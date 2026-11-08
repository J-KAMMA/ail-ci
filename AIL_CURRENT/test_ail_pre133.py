"""Regressions for differences a reviewer found before job errmsgoc.

1. A non-empty container class attribute (`class A__B: n = {1: 2}` / `n = [1, 2]`) is read
   through the class and through an instance like CPython; the class body is not refused and
   the value is not copied per instance.
2. The Fraction prelude returns tuples (`as_integer_ratio`, `__divmod__`, `__rdivmod__`).  The
   tuple pass used to leave `cannot tell the type of element 0 of this tuple` notes for those
   prelude lines whenever the user program was refused for an unrelated reason, and the notes
   pointed at line numbers past the user's file.  The prelude now names the element types, so a
   refusal shows only its own note, and the returned tuples still match CPython on both builds.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
POPROW = (ROOT.parent / 'lab' / 'err' / 'triggers' / '02_poprow_arity.py').read_text(
    encoding='utf-8')
FRACTION_NOTE = 'from fractions import Fraction\nx = Fraction(1, 2)\nprint(float(x))\n'
DECIMAL_NOTE = 'from decimal import Decimal\nd = Decimal("1.234")\nprint(f"{d:.2f}")\n'

CLASS_ATTRS = r'''class A__B:
    n = {1: 2}
    m = [1, 2]


class A__C:
    n = {1: 2}
    m = [1, 2]
    s = {1, 2}
    t = (1, 2)


def main():
    print(A__B.n, A__B.m, len(A__B.n), len(A__B.m))
    a = A__C()
    print(a.n, a.m, sorted(a.s), a.t)
    print(a.m is A__C.m, A__C.n is a.n)
    a.n = {3: 4}
    print(a.n, A__C.n)


main()
'''

FRACTION = r'''from fractions import Fraction


def main():
    for a in [Fraction(7, 3), Fraction(-7, 3), Fraction(0), Fraction(5)]:
        print(a.as_integer_ratio())
        for b in [Fraction(2), Fraction(2, 5), Fraction(-3, 7), 2, -3]:
            if b != 0:
                q, r = divmod(a, b)
                print(q, r)
                print(divmod(a, b))
        for b in [2, -3, Fraction(4, 3)]:
            if a != 0:
                print(divmod(b, a), divmod(1.5, a))
            print(divmod(a, 1.5))


main()
'''

REFUSED = 'from fractions import Fraction\nprint(eval("1"))\n'


def cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, *, general, quiet=True, suffix='.ail'):
    src = Path(directory) / (name + suffix)
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    if quiet:
        env['AIL_QUIET_FALLBACK'] = '1'
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env)
    return done, exe


class Pre133Tests(unittest.TestCase):
    def test_container_class_attributes_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre133-') as directory:
            want, rc, err = cpython(directory, 'attrs', CLASS_ATTRS)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                done, exe = build(directory, 'attrs_%s' % ('g' if general else 'd'), CLASS_ATTRS,
                                  general=general)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                 got.stderr.decode('utf-8', 'replace'))
                self.assertEqual(got.returncode, 0)

    def test_fraction_tuple_returns_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre133-') as directory:
            want, rc, err = cpython(directory, 'frac', FRACTION)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                done, exe = build(directory, 'frac_%s' % ('g' if general else 'd'), FRACTION,
                                  general=general)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                 got.stderr.decode('utf-8', 'replace'))
                self.assertEqual(got.returncode, 0)

    def test_poprow_note_names_the_users_rows(self):
        # implementation step 2: a name bound from heaps of two row widths used to report a
        # compiler temporary (`_ail_l1l`).  The note now names the user's variable and every heap
        # it was popped from, at a position inside the user's file.
        with tempfile.TemporaryDirectory(prefix='ail-pre133-') as directory:
            done, _ = build(directory, 'poprow', POPROW, general=False, quiet=False)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertNotIn('_ail_', done.stderr)
            note = next((line for line in done.stderr.splitlines() if 'popping rows' in line), '')
            self.assertTrue(note, done.stderr)
            self.assertIn("'entry'", note)
            for heap in ('departures', 'wait1', 'wait2', 'wait3'):
                self.assertIn(heap, note)
            where = re.search(r':(\d+):(\d+):', note)
            self.assertIsNotNone(where, note)
            self.assertLessEqual(int(where.group(1)), len(POPROW.splitlines()))

    def test_prelude_note_points_at_the_users_call(self):
        # A refusal raised while loading `fractions`/`decimal` was reported at a line of the
        # prelude (235, 1687).  The note now names the user's call and the module it came from.
        cases = (('frac_note', FRACTION_NOTE, 'fractions', 'dunder'),
                 ('dec_note', DECIMAL_NOTE, 'decimal', 'format spec'))
        for name, text, module, marker in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(prefix='ail-pre133-') as directory:
                    # a `.py` entry: the prelude-unit table is recorded for Python-syntax entries
                    done, _ = build(directory, name, text, general=False, quiet=False,
                                    suffix='.py')
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                    note = next((line for line in done.stderr.splitlines() if marker in line), '')
                    self.assertTrue(note, done.stderr)
                    self.assertIn("standard library's %s module" % module, note)
                    where = re.search(r':(\d+):(\d+):', note)
                    self.assertIsNotNone(where, note)
                    self.assertEqual(int(where.group(1)), 3, note)
                    self.assertNotIn(':235:', note)
                    self.assertNotIn(':1687:', note)

    def test_fraction_prelude_adds_no_tuple_notes_to_a_refusal(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre133-') as directory:
            for general in (True, False):
                done, _ = build(directory, 'refused_%s' % ('g' if general else 'd'), REFUSED,
                                general=general)
                self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
                self.assertIn("the name 'eval' is not a known function/class/builtin", done.stderr)
                self.assertNotIn('cannot tell the type of element', done.stderr)


if __name__ == '__main__':
    unittest.main()
