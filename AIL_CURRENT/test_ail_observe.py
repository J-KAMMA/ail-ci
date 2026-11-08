"""`ail_observe.py`: the run-time kind recorder and the observed-annotation writer (job obs1).

The recorder runs a program once under CPython and must not change its output.  Per function it
counts calls, keeps self time and records the kinds of arguments, returns and yields, sampling
container elements; the annotator writes an observed monomorphic kind as an annotation and edits
nothing but annotation text.  A polymorphic slot, a user class and a slot never seen stay
unannotated.  The default build is not involved.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ail_observe as obs  # noqa: E402

PROGRAM = textwrap.dedent('''
    class Box:
        def __init__(self, v):
            self.v = v

        def get(self):
            return self.v


    def add(a, b):
        return a + b


    def poly(x):
        return x


    def total(xs):
        s = 0
        for x in xs:
            s += x
        return s


    def words(d):
        return sorted(d)


    def pair(t):
        return t[0]


    def gen(n):
        for i in range(n):
            yield i * 0.5


    def boom(n):
        if n > 2:
            raise ValueError(n)
        return n


    def fact(n):
        return 1 if n <= 1 else n * fact(n - 1)


    def unused(q):
        return q


    def main():
        print(add(1, 2), add(3, 4))
        print(poly(1), poly("s"))
        print(total([1, 2, 3]), total([]))
        print(words({"a": 1, "b": 2}))
        print(pair((1, "x")))
        print(sum(gen(4)))
        try:
            boom(5)
        except ValueError as e:
            print("caught", e)
        print(boom(1))
        print(Box(3).get())
        print(fact(25))
        print(add(1 << 70, 1))


    main()
''')


class ObserveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ail-observe-test-')
        cls.dir = Path(cls.tmp.name)
        cls.script = cls.dir / 'prog.py'
        cls.script.write_text(PROGRAM, encoding='utf-8')
        cls.prof = cls.dir / 'p.json'
        plain = subprocess.run([sys.executable, '-B', str(cls.script)], capture_output=True,
                               cwd=str(cls.dir))
        seen = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_observe.py'), 'run',
                               '--exact-time', '-o', str(cls.prof), str(cls.script)],
                              capture_output=True,
                              cwd=str(cls.dir))
        cls.plain, cls.seen = plain, seen
        cls.data = json.loads(cls.prof.read_text())
        cls.rows = obs.functions_for(cls.data, str(cls.script))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def kinds(self, qual, param):
        for p in self.rows[qual]['params']:
            if p['name'] == param:
                return p['kinds']
        raise KeyError(param)

    def test_output_unchanged(self):
        self.assertEqual(self.seen.returncode, 0, self.seen.stderr)
        self.assertEqual(self.seen.stdout, self.plain.stdout)

    def test_schema_and_tool(self):
        self.assertEqual(self.data['schema'], obs.SCHEMA)
        self.assertIn(self.data['tool'], ('sys.monitoring', 'sys.setprofile'))
        if sys.version_info >= (3, 12):
            self.assertEqual(self.data['tool'], 'sys.monitoring')

    def test_scalar_kinds_and_counts(self):
        self.assertEqual(self.rows['add']['calls'], 3)
        self.assertEqual(self.kinds('add', 'a'), {'int': 3})
        self.assertEqual(self.rows['add']['returns'], {'int': 3})
        self.assertEqual(self.kinds('poly', 'x'), {'int': 1, 'str': 1})

    def test_big_int_flag(self):
        big = [p['big'] for p in self.rows['add']['params'] if p['name'] == 'a'][0]
        self.assertEqual(big, 1)

    def test_container_kinds(self):
        self.assertEqual(self.kinds('total', 'xs'), {'list[int]': 1, 'list[?]': 1})
        self.assertEqual(self.kinds('words', 'd'), {'dict[str, int]': 1})
        self.assertEqual(self.kinds('pair', 't'), {'tuple[int, str]': 1})
        self.assertEqual(self.rows['words']['returns'], {'list[str]': 1})

    def test_generator_exception_recursion_method(self):
        g = self.rows['gen']
        self.assertTrue(g['generator'])
        self.assertEqual(g['calls'], 1)
        self.assertEqual(g['yields'], {'float': 4})
        self.assertEqual(self.rows['boom']['raised'], 1)
        self.assertEqual(self.rows['boom']['returns'], {'int': 1})
        self.assertEqual(self.rows['fact']['calls'], 25)
        self.assertEqual(self.rows['Box.get']['returns'], {'int': 1})
        self.assertTrue(any(k.startswith('cls:') for k in self.kinds('Box.get', 'self')))
        self.assertNotIn('unused', self.rows)

    def test_self_time_is_sane(self):
        total = sum(r['self_s'] for r in self.rows.values())
        self.assertGreater(total, 0)
        self.assertLessEqual(total, self.data['wall_s'] * 1.05)
        self.assertTrue(all(r['self_s'] >= 0 for r in self.rows.values()))

    def _busy(self, *flags):
        script = self.dir / 'busy.py'
        script.write_text(textwrap.dedent('''
            def leaf(i):
                return i & 7

            def hot(n):
                s = 0
                for i in range(n):
                    s += i * i % 7
                return s

            def calls(n):
                t = 0
                for i in range(n):
                    t += leaf(i)
                return t

            print(hot(300000), calls(5000), [leaf(1), leaf("x" if False else 2)])
        '''), encoding='utf-8')
        prof = self.dir / ('busy%s.json' % len(flags))
        r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_observe.py'), 'run', *flags,
                            '-o', str(prof), str(script)], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(prof.read_text())
        return data, {v['qualname']: v for v in data['functions'].values()}

    def test_sampled_time_and_counts(self):
        data, rows = self._busy()
        if data['timing'] != 'sample':
            self.skipTest('no SIGPROF sampler here')
        self.assertTrue(data['calls_exact'])
        self.assertEqual(rows['leaf']['calls'], 5002)
        self.assertGreater(data['ticks'], 0)
        # the CPU-bound loop owns most of the samples
        self.assertGreater(rows['hot']['ticks'], rows['calls']['ticks'])
        # return sites are sampled within a budget, not on every call
        self.assertLess(sum(rows['leaf']['returns'].values()), 5002)
        self.assertEqual(set(rows['leaf']['returns']), {'int'})

    def test_fast_mode_counts_are_lower_bounds(self):
        data, rows = self._busy('--fast')
        if data['timing'] != 'sample':
            self.skipTest('no SIGPROF sampler here')
        self.assertFalse(data['calls_exact'])
        self.assertGreaterEqual(rows['leaf']['calls'], 1024)
        self.assertLessEqual(rows['leaf']['calls'], 5002)
        self.assertEqual(rows['leaf']['params'][0]['kinds'], {'int': rows['leaf']['sampled_calls']})

    def test_kind_of_samples_and_unions(self):
        self.assertEqual(obs.kind_of([1, 'a']), 'list[int|str]')
        self.assertEqual(obs.kind_of([[1], [2]]), 'list[list[int]]')
        self.assertEqual(obs.kind_of(tuple(range(20))), 'tuple[int, ...]')
        self.assertEqual(obs.kind_of(set()), 'set[?]')
        self.assertEqual(obs.kind_of(None), 'None')
        self.assertEqual(obs.kind_of(True), 'bool')
        # a long list is sampled, not scanned: a str hidden between samples is not seen
        xs = list(range(1000))
        xs[1] = 'hidden'
        self.assertEqual(obs.kind_of(xs), 'list[int]')

    def test_slot_verdicts(self):
        self.assertEqual(obs.slot_verdict({'int': 3}), ('mono', 'int'))
        self.assertEqual(obs.slot_verdict({'list[int]': 1, 'list[?]': 1}), ('mono', 'list[int]'))
        self.assertEqual(obs.slot_verdict({'int': 1, 'str': 1})[0], 'poly')
        self.assertEqual(obs.slot_verdict({'cls:m.Box': 1})[0], 'unexpressible')
        self.assertEqual(obs.slot_verdict({'list[?]': 2})[0], 'unexpressible')
        self.assertEqual(obs.slot_verdict({})[0], 'unseen')

    def test_annotate_only_touches_annotations(self):
        new, dec = obs.annotate_source(PROGRAM, self.rows)
        self.assertIn('def add(a: int, b: int) -> int:', new)
        self.assertIn('def total(xs: list[int]) -> int:', new)
        self.assertIn('def poly(x):', new)                      # polymorphic: left alone
        self.assertIn('def unused(q):', new)                    # never called
        self.assertIn('def gen(n: int):', new)                  # generator: no return kind
        self.assertIn('def get(self) -> int:', new)             # user class not written
        self.assertEqual(dec['poly']['params']['x']['verdict'], 'poly')
        # removing the added text gives back the original bytes
        import re
        back = re.sub(r': (int|str|float|bool|list\[[^\]]*\]|dict\[[^\]]*\]|tuple\[[^\]]*\])'
                      r'(?=[,)])', '', new)
        back = re.sub(r' -> [^:]+:', ':', back)
        self.assertEqual(back, PROGRAM)
        # the annotated program still runs and prints the same bytes
        path = self.dir / 'annotated.py'
        path.write_text(new, encoding='utf-8')
        run = subprocess.run([sys.executable, '-B', str(path)], capture_output=True)
        self.assertEqual(run.stdout, self.plain.stdout)

    def test_strip_then_annotate_and_keep(self):
        typed = 'def f(a: int, b=2, *c: str, d: "x" = 1) -> list[int]:\n    y: int = a\n    return [y]\n'
        self.assertEqual(obs.strip_source(typed),
                         'def f(a, b=2, *c, d = 1):\n    y = a\n    return [y]\n')
        rows = {'f': {'qualname': 'f', 'generator': False,
                      'params': [{'name': 'a', 'kinds': {'float': 1}, 'big': 0},
                                 {'name': 'b', 'kinds': {'int': 1}, 'big': 0}],
                      'returns': {'list[int]': 1}}}
        kept, _ = obs.annotate_source(typed, rows)
        self.assertTrue(kept.startswith('def f(a: int, b: int=2,'))  # a keeps the hand kind
        bare, _ = obs.annotate_source(typed, rows, strip=True)
        self.assertTrue(bare.startswith('def f(a: float, b: int=2, *c, d = 1) -> list[int]:'))

    def test_cli_strip_and_annotate(self):
        out = self.dir / 'cli.py'
        r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_observe.py'), 'annotate',
                            str(self.prof), str(self.script), '-o', str(out)], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('def add(a: int, b: int) -> int:', out.read_text())

    def test_setprofile_fallback(self):
        rec = obs.Recorder()
        rec.tool = 'sys.setprofile'
        rec._t0 = 0
        import time as _t
        rec._t0 = _t.perf_counter()
        sys.setprofile(rec._profile_hook)
        try:
            def sq(v):
                return v * v
            for i in range(5):
                sq(i)
        finally:
            sys.setprofile(None)
        rows = {r['qualname']: r for r in rec.report()['functions'].values()}
        key = [q for q in rows if q.endswith('sq')][0]
        self.assertEqual(rows[key]['calls'], 5)
        self.assertEqual(rows[key]['params'][0]['kinds'], {'int': 5})
        self.assertEqual(rows[key]['returns'], {'int': 5})


if __name__ == '__main__':
    unittest.main()
