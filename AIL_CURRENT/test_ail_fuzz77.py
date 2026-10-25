"""Differential fuzz round 77: any/all over generators, filter(None) and map over several iterables.

Found with small random programs compared against CPython on both builds:

1. `any(f(x) for x in xs)` / `all(f(x) for x in xs)` evaluated EVERY element of the generator
   before deciding.  The general path fused a GeneratorExp into the consumer loop (skipping the
   materialised list and the second scan) but only recorded the result and never left the loop,
   so side effects after the deciding element still ran and exceptions in them were still raised:
   `any(hit(log, v) for v in [0, 0, 3, 4, 0])` logged `[0, 0, 3, 4, 0]` where CPython logs
   `[0, 0, 3]`.  The fused path now leaves every enclosing comprehension loop with a `goto` at
   the first deciding element, which is exactly CPython's short circuit for a generator.

The rest of the programs below (empty iterables, nested generator clauses, filter(None), map over
iterables of different lengths, huge/negative ranges, wrong types) are kept compared with CPython
on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GEN_SHORT_CIRCUIT = r'''def hit(log: list[int], v: int) -> bool:
    log.append(v)
    return v != 0


def main() -> None:
    a: list[int] = []
    print(any(hit(a, v) for v in [0, 0, 3, 4, 0]), a)
    b: list[int] = []
    print(all(hit(b, v) for v in [1, 2, 0, 5]), b)
    c: list[int] = []
    print(any(hit(c, v) for v in []), c)
    d: list[int] = []
    print(all(hit(d, v) for v in []), d)
    e: list[int] = []
    print(any(hit(e, x * y) for x in [1, 2, 0, 4] for y in [1, 2, 3] if x > 0), e)
    f: list[int] = []
    print(all(hit(f, x * y) for x in [1, 2, 3] for y in [1, -1, 2]), f)
    g: dict[str, int] = {"a": 0, "b": 1, "c": 4}
    h: list[int] = []
    print(any(hit(h, v) for v in g.values()), h)
    i: list[int] = []
    print(any(hit(i, v) for v in map(abs, [-0, 0, 3, 4])), i)
    j: list[int] = []
    print(all(hit(j, v) for v in filter(None, [1, 2, 0, 5])), j)


main()
'''

GEN_EXCEPTION_POSITION = r'''def boom(x: int) -> bool:
    if x == 0:
        raise ValueError("zero")
    return x > 1


def main() -> None:
    try:
        print(any(boom(x) for x in [1, 2, 0, 1]))
    except ValueError:
        print("any-raised")
    try:
        print(all(boom(x) for x in [1, 0, 5]))
    except ValueError:
        print("all-raised")
    try:
        print(any(boom(x) for x in [0]))
    except ValueError:
        print("any-first-raised")
    print(all(boom(x) for x in [1, 2]))


main()
'''

GEN_VALUES_THROUGH_OBJECTS = r'''class Acc:
    log: list[int]

    def __init__(self) -> None:
        self.log = []

    def hit(self, v: int) -> bool:
        self.log.append(v)
        return v != 0


class Item:
    flag: int

    def __init__(self, f: int) -> None:
        self.flag = f


def check(acc: Acc, xs: list[int]) -> bool:
    return any(acc.hit(v) for v in xs)


def main() -> None:
    acc: Acc = Acc()
    print(check(acc, [0, 0, 5, 6]), acc.log)
    items: list[Item] = [Item(0), Item(0), Item(3), Item(4)]
    acc2: Acc = Acc()
    print(any(acc2.hit(it.flag) for it in items), acc2.log)
    d: dict[str, Item] = {"a": Item(0), "b": Item(2), "c": Item(3)}
    acc3: Acc = Acc()
    print(all(acc3.hit(it.flag) for it in d.values()), acc3.log)
    xs: list[int] = [0, 0, 7]
    acc4: Acc = Acc()
    print(any(acc4.hit(xs[i]) for i in range(len(xs))), acc4.log)


main()
'''

FILTER_NONE = r'''def main() -> None:
    print(list(filter(None, {})))
    print(list(filter(None, {"a": 1})))
    print(list(filter(None, set())))
    print(list(filter(None, {0, 1, 2})))
    print(list(filter(None, range(-3, 4))))
    print(list(filter(None, "a\x00bc")))
    print(list(filter(None, (x for x in [0, 3, 0, 4]))))
    print(list(filter(lambda x: x < 0, [-2, -1, 0, 1])))
    vals: dict[str, int] = {"z": 0, "o": 1}
    print(list(filter(None, vals.values())))


main()
'''

MAP_SEVERAL = r'''def add(a: int, b: int) -> int:
    return a + b


def main() -> None:
    xs: list[int] = [1, 2, 3]
    ys: list[int] = [10, 20]
    m = map(add, xs, ys)
    print(list(m))
    print(list(map(add, [], ys)))
    print(list(map(add, xs, [])))
    print(list(map(add, xs, [10, 20, 30])))
    print(list(map(lambda a, b: a - b, xs, [1])))
    print(sum(map(add, xs, ys)))
    z = map(add, xs, [7])
    for v in z:
        print(v)


main()
'''

EMPTY_HUGE_NEGATIVE = r'''def main() -> None:
    print(any(x for x in range(1000000)), all(x for x in range(1000000)))
    print(any(x < 0 for x in range(-3, 3)), all(x < 3 for x in range(-3, 3)))
    print(any(x for x in range(0)), all(x for x in range(0)))
    e: list[int] = []
    d: dict[str, int] = {}
    s: set[int] = set()
    print(any(e), all(e), any(d), all(d), any(s), all(s))
    print(any([[]]), all([[]]), any([[0]]), all([[1]]))


main()
'''

ANY_WRONG_TYPE = r'''def main() -> None:
    print(any(1))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz77Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz77-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_genexpr_any_all_short_circuit(self):
        self.check('gen_short', GEN_SHORT_CIRCUIT)

    def test_genexpr_exception_position(self):
        self.check('gen_exc', GEN_EXCEPTION_POSITION)

    def test_genexpr_values_through_objects(self):
        self.check('gen_objects', GEN_VALUES_THROUGH_OBJECTS)

    def test_filter_none(self):
        self.check('filter_none', FILTER_NONE)

    def test_map_several_iterables(self):
        self.check('map_several', MAP_SEVERAL)

    def test_empty_huge_negative(self):
        self.check('empty_huge', EMPTY_HUGE_NEGATIVE)

    def test_any_wrong_type_is_cpython_error(self):
        self.check('any_wrong', ANY_WRONG_TYPE, rc=1)


if __name__ == '__main__':
    unittest.main()
