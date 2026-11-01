"""walkmemo: the memo tables of the general path change the time of a build, never its result.

W1  marks(): the same answer as bigcap.marked / bigcap.own_marked, kept per tree CONTENT (an edited tree misses), and a
    hit is a copy the caller may change
W2  a refusal of pyboxed2.build is raised again for the same source/mode/environment without building again; a build with
    typed clones off reuses it only when the first build wired none; AIL_NO_WALKMEMO=1 builds again
W4  mix_report(): pymix.analyze runs once per source and environment; a raising analysis is not remembered
W3  the C text of a general-path program is the same with the tables on, with them warm, and with AIL_NO_WALKMEMO=1
"""
import ast
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))

PROGRAM = '''
def tally(words):
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return counts

def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a

def shift(n):
    return 1 << n

def main():
    print(sorted(tally("a b a c b a".split()).items()))
    print(shift(70), gcd(84, 36))

main()
'''


class Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.patch = mock.patch.dict(os.environ, self.kv)
        self.patch.start()
        import walkmemo
        walkmemo._MARKS.clear()
        walkmemo._FAILS.clear()
        walkmemo._MIX.clear()

    def __exit__(self, *exc):
        self.patch.stop()


class MarksTests(unittest.TestCase):
    def test_w1_same_answer_keyed_by_content(self):
        import bigcap
        import walkmemo
        with Env(AIL_SURFACE='python', AIL_EXACT_INT='1'):
            tree = ast.parse(PROGRAM)
            for own in (False, True):
                for local in (True, False):
                    direct = bigcap.own_marked(tree, local) if own else bigcap.marked(tree, local)
                    self.assertEqual(walkmemo.marks(tree, own, local=local), direct)
                    self.assertEqual(walkmemo.marks(tree, own, local=local), direct)       # a hit
            self.assertTrue(walkmemo.marks(tree, False, local=False))                      # `1 << n` is marked
            first = walkmemo.marks(tree, False)
            first['x'] = 'changed by the caller'
            self.assertNotIn('x', walkmemo.marks(tree, False))
            # the same object, edited in place: not the old answer
            edited = ast.parse(PROGRAM.replace('1 << n', '1 + n'))
            self.assertEqual(walkmemo.marks(edited, False, local=False), bigcap.marked(edited, False))
            tree.body = edited.body
            self.assertEqual(walkmemo.marks(tree, False, local=False), bigcap.marked(tree, False))

    def test_w1_environment_is_part_of_the_key(self):
        import bigcap
        import walkmemo
        with Env(AIL_SURFACE='python', AIL_EXACT_INT='1'):
            tree = ast.parse(PROGRAM)
            on = walkmemo.marks(tree, False)
            with mock.patch.dict(os.environ, {'AIL_SURFACE': 'ail'}):
                self.assertEqual(walkmemo.marks(tree, False), bigcap.marked(tree))
                self.assertEqual(walkmemo.marks(tree, False), {})
            self.assertEqual(walkmemo.marks(tree, False), on)


class FailureTests(unittest.TestCase):
    def test_w2_refusal_repeats_without_building(self):
        import pyboxed2
        from pyfront import Unsupported
        calls = []

        def refuse(source, report, allow_mix=True):
            calls.append(allow_mix)
            error = Unsupported('the method .match() (on a value of unknown static kind)')
            error.source_line = 7
            error._mix_inert = True
            raise error
        with Env(AIL_SURFACE='python'), mock.patch.object(pyboxed2, '_build', refuse):
            with self.assertRaises(Unsupported) as first:
                pyboxed2.build('x = 1\n', {})
            with self.assertRaises(Unsupported) as again:
                pyboxed2.build('x = 1\n', {})
            self.assertEqual(calls, [True])
            self.assertEqual(str(again.exception), str(first.exception))
            self.assertEqual(again.exception.source_line, 7)
            self.assertIsNot(again.exception, first.exception)
            with self.assertRaises(Unsupported):
                pyboxed2.build('x = 1\n', {}, allow_mix=False)       # no clone wired: the same refusal
            self.assertEqual(calls, [True])
            with self.assertRaises(Unsupported):
                pyboxed2.build('x = 2\n', {})                         # another source
            self.assertEqual(calls, [True, True])
            with mock.patch.dict(os.environ, {'AIL_BIGINT': 'off'}), self.assertRaises(Unsupported):
                pyboxed2.build('x = 1\n', {})                         # another environment
            self.assertEqual(len(calls), 3)

    def test_w2_wired_clone_is_not_reused_for_a_mixless_build(self):
        import pyboxed2
        from pyfront import Unsupported
        calls = []

        def refuse(source, report, allow_mix=True):
            calls.append(allow_mix)
            error = Unsupported('boom')
            error._mix_inert = False
            raise error
        with Env(AIL_SURFACE='python'), mock.patch.object(pyboxed2, '_build', refuse):
            for _ in range(2):
                with self.assertRaises(Unsupported):
                    pyboxed2.build('x = 1\n', {})
            with self.assertRaises(Unsupported):
                pyboxed2.build('x = 1\n', {}, allow_mix=False)
            self.assertEqual(calls, [True, False])

    def test_w2_switch_off_builds_every_time(self):
        import pyboxed2
        from pyfront import Unsupported
        calls = []

        def refuse(source, report, allow_mix=True):
            calls.append(1)
            raise Unsupported('boom')
        with Env(AIL_SURFACE='python', AIL_NO_WALKMEMO='1'), mock.patch.object(pyboxed2, '_build', refuse):
            for _ in range(3):
                with self.assertRaises(Unsupported):
                    pyboxed2.build('x = 1\n', {})
            self.assertEqual(len(calls), 3)


class MixReportTests(unittest.TestCase):
    def test_w4_analysis_runs_once(self):
        import walkmemo

        class Fake:
            calls = 0
            fail = False

            def analyze(self, source):
                Fake.calls += 1
                if Fake.fail:
                    raise ValueError('boom')
                return object()
        fake = Fake()
        with Env(AIL_SURFACE='python'):
            first = walkmemo.mix_report(fake, 'x = 1\n')
            self.assertIs(walkmemo.mix_report(fake, 'x = 1\n'), first)
            self.assertEqual(Fake.calls, 1)
            self.assertIsNot(walkmemo.mix_report(fake, 'x = 2\n'), first)
            self.assertEqual(Fake.calls, 2)
            with mock.patch.dict(os.environ, {'AIL_NO_MIX': '1'}):
                walkmemo.mix_report(fake, 'x = 1\n')
            self.assertEqual(Fake.calls, 3)
            Fake.fail = True
            for _ in range(2):
                with self.assertRaises(ValueError):
                    walkmemo.mix_report(fake, 'x = 3\n')
            self.assertEqual(Fake.calls, 5)
        with Env(AIL_SURFACE='python', AIL_NO_WALKMEMO='1'):
            Fake.fail = False
            walkmemo.mix_report(fake, 'x = 1\n')
            walkmemo.mix_report(fake, 'x = 1\n')
            self.assertEqual(Fake.calls, 7)


class SameCTests(unittest.TestCase):
    def test_w3_c_text_is_unchanged(self):
        import pyboxed2
        reports = []
        with Env(AIL_SURFACE='python', AIL_NO_WALKMEMO='1'):
            reports.append({})
            plain = pyboxed2.build(PROGRAM, reports[-1])
        with Env(AIL_SURFACE='python'):
            reports.append({})
            cold = pyboxed2.build(PROGRAM, reports[-1])
            reports.append({})
            warm = pyboxed2.build(PROGRAM, reports[-1])
        self.assertEqual(plain, cold)
        self.assertEqual(plain, warm)
        for key in ('mix_units', 'typed_inline', 'boxed', 'bigint'):
            self.assertEqual(reports[0].get(key), reports[1].get(key))
            self.assertEqual(reports[0].get(key), reports[2].get(key))


if __name__ == '__main__':
    unittest.main()
