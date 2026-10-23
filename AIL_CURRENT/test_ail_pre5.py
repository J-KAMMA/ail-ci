"""`reversed(d)` on a dict (pre-existing difference recorded by the fuzz73 review).

CPython returns the dict's keys in reverse insertion order; both AIL builds used to raise
`TypeError: 'dict' object is not reversible`. The runtime now has a dict case that reads the
dense entry array from the end, with CPython's size check (`dictionary changed size during
iteration`) at every step. Each program below is compared with CPython 3.12 on the general
path and on the default build (IR 0 and 1).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r"""print(list(reversed({})))
print(list(reversed({'only': 1})))
d = {'a': 1, 'b': 2, 'c': 3}
print(list(reversed(d)))
print([k for k in reversed(d)])
for k in reversed(d):
    print('it', k, d[k])
it = reversed(d)
print(next(it), next(it), next(it))
try:
    next(it)
except StopIteration:
    print('stopped')
ints = {3: 'c', -1: 'a', 2**62: 'wide', -(2**62): 'neg', 0: 'z'}
print(list(reversed(ints)))
weird = {None: 1, True: 2, (1, 'x'): 3, -2.5: 4, '': 5}
print(list(reversed(weird)))
uni = {'': 0, 'é': 1, '東京': 2, 'ß': 3}
print(list(reversed(uni)))
print(list(reversed({False: 'f', True: 't'})))
d2 = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
del d2['b']
d2['a'] = 10
d2['e'] = 5
print(list(reversed(d2)), list(d2))
"""

CONTAINERS = r"""def rev(d):
    return list(reversed(d))


class Box:
    def __init__(self, d):
        self.d = d


class Map:
    def __init__(self):
        self.data = {'x': 1, 'y': 2, 'z': 3}


def main():
    d = {'p': 1, 'q': 2}
    print(rev(d))
    ds = [{'m': 1}, {'n': 2, 'o': 3}]
    print(list(reversed(ds[1])))
    b = Box({'u': 1, 'v': 2})
    print(list(reversed(b.d)))
    top = {'inner': {'i': 1, 'j': 2}, 'other': 0}
    print(list(reversed(top['inner'])))
    print(list(reversed(top)))
    alias = d
    alias['r'] = 3
    print(list(reversed(d)), list(reversed(alias)))
    print(list(reversed(Map().data)))
    print(list(reversed({k: k * 2 for k in range(5)})))
    from collections import defaultdict
    dd = defaultdict(list)
    dd['a'].append(1)
    dd['b'].append(2)
    print(list(reversed(dd)))
    big = {i: i * i for i in range(200)}
    revbig = list(reversed(big))
    print(len(revbig), revbig[:3], revbig[-3:])


main()
"""

TYPED = r"""def rev(d: dict[str, int]) -> list[str]:
    return list(reversed(d))


def walk(d: dict[str, int]) -> None:
    for k in reversed(d):
        print(k, d[k])


class Bag:
    def __init__(self) -> None:
        self.items: dict[str, int] = {}

    def add(self, k: str, v: int) -> None:
        self.items[k] = v


def main() -> None:
    d: dict[str, int] = {}
    print(rev(d))
    d['a'] = 1
    print(rev(d))
    d['b'] = 2
    d['c'] = 3
    walk(d)
    b = Bag()
    b.add('x', 10)
    b.add('y', 20)
    print(rev(b.items))
    all_d: dict[str, dict[str, int]] = {'inner': d}
    print(rev(all_d['inner']))
    print(rev({str(i): i for i in range(5)}))


main()
"""

MUTATION = r"""def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)


d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['c']
show('del', lambda: next(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
d['z'] = 9
show('add', lambda: next(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['c']
d['z'] = 9
show('replace', lambda: list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
d['a'] = 99
show('value', lambda: list(it))

d = {'a': 1, 'b': 2}
it = reversed(d)
d['x'] = 1
del d['x']
show('add-del-same-size', lambda: next(it))

d = {'a': 1, 'b': 2}
it = reversed(d)
d.clear()
d['x'] = 1
d['y'] = 2
show('clear-refill-same-size', lambda: next(it))

d = {}
it = reversed(d)
show('empty-next', lambda: next(it))
show('empty-list', lambda: list(it))

d = {'a': 1, 'b': 2}
it = reversed(d)
print(list(it))
show('exhausted', lambda: next(it))
d['c'] = 3
show('exhausted-after-change', lambda: next(it))

d = {}
it = reversed(d)
d['a'] = 1
show('empty-then-add', lambda: next(it))

d = {'a': 1}
it = reversed(d)
print(next(it))
d['b'] = 2
show('yielded-all-then-add', lambda: next(it))

d = {'a': 1}
it = reversed(d)
print(list(it))
d['b'] = 2
show('list-exhausted-then-add', lambda: next(it))

d = {'a': 1}
it = reversed(d)
print(next(it))
try:
    next(it)
except StopIteration:
    print('marked-exhausted')
d['b'] = 2
show('exhausted-then-add', lambda: next(it))
"""

SAMESIZE = r"""d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['a']
d['a'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['a']
d['z'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['b']
d['b'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
del d['b']
d['z'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
it = reversed(d)
print(next(it))
del d['a']
del d['b']
d['x'] = 8
d['y'] = 9
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
k, v = d.popitem()
d[k] = v
print(list(it))

d = {'a': 1, 'b': 2, 'c': 3}
it = reversed(d)
print(next(it))
d['z'] = 9
try:
    next(it)
except RuntimeError:
    print('size error')
del d['z']
try:
    next(it)
except RuntimeError:
    print('size error stays')
"""

CASES = [
    ('basic', BASIC),
    ('containers', CONTAINERS),
    ('typed', TYPED),
    ('mutation', MUTATION),
    ('samesize', SAMESIZE),
]


def build(directory, text, name, ir, general):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_IR=ir)
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class ReversedDict(unittest.TestCase):
    def check(self, slug, text, ir, general):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, 'oracle.py')
            oracle.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, str(oracle)], capture_output=True, timeout=300)
            self.assertEqual(want.returncode, 0, want.stderr)
            built, exe = build(directory, text, slug, ir, general)
            self.assertEqual(built.returncode, 0, built.stdout[-1000:] + built.stderr[-2000:])
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-1000:])
            self.assertEqual(got.stdout.decode('utf-8', 'replace'), want.stdout.decode('utf-8', 'replace'), slug)

    def test_general_path(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, '0', True)

    def test_default_build(self):
        for ir in ('0', '1'):
            for slug, text in CASES:
                with self.subTest(slug=slug, ir=ir):
                    self.check(slug + '_ir' + ir, text, ir, False)


if __name__ == '__main__':
    unittest.main()
