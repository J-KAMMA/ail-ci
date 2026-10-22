# -*- coding: utf-8 -*-
"""C118: a NaN the source never spells (made by arithmetic on an overflow, `big - big`) keeps its identity in a
container search (`count`, `index`, `remove`, `in`, `==`, dict lookup) in the default build (AIL_UNIFIED on) and with
AIL_UNIFIED=0. unified.float_search_risk keeps every float boxed in a program that searches with a value that may be
a float; a program whose searches are all float-free keeps its floats unboxed (the cost)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_ail_silent2 import CHATGPT, HAVE_CC, check_program

CASES = {'arith_list': 'def main():\n    big = 1e308 * 10\n    m = big - big\n    xs = [m, 1.0]\n    print(xs.count(m), xs.index(m), xs.count(1.0))\n    ys = [1.0, m, 2.0]\n    ys.remove(m)\n    print(len(ys), ys.index(2.0))\n    print(m in xs, [m] == [m], m in (m, 1.0))\n\n\nmain()\n', 'argument_item_attr_value': "class S:\n    def __init__(self, v):\n        self.v = v\n        self.xs = [v, 1.5]\n\n\ndef nanof(z):\n    return z - z\n\n\ndef probe(v, xs):\n    return xs.count(v), v in xs, xs.index(v) if v in xs else -1\n\n\ndef main():\n    n = nanof(1e308 * 10)\n    s = S(n)\n    print(probe(n, [n, 1.0]), probe(n, []), probe(s.v, s.xs), probe(s.v, [nanof(1e308 * 10)]))\n    d = {'a': n}\n    items = [n, n]\n    print(probe(d['a'], [n]), probe(items[1], items), items == items, items == [n, n])\n\n\nmain()\n", 'dataclass_dict': 'from dataclasses import dataclass\n\n\n@dataclass\nclass W:\n    v: float\n\n\n@dataclass(frozen=True)\nclass F:\n    v: float\n\n\ndef main():\n    m = (1e308 * 10) - (1e308 * 10)\n    a, b = W(m), W(m)\n    print(a == b, a != b, a in [b], [a].count(b))\n    d = {F(m): 1}\n    print(F(m) in d, d.get(F(m)), d[F(m)])\n    t = {(m, 1): 5}\n    print(t[(m, 1)], (m, 1) in t)\n\n\nmain()\n', 'dict_key': 'def main():\n    m = (1e308 * 10) - (1e308 * 10)\n    d = {m: 1, 2.5: 2}\n    print(d.get(m), d[m], d.get(2.5), d.pop(m), len(d))\n    e = {}\n    e[m] = 5\n    e[m] += 1\n    print(len(e), e[m], e.setdefault(m, 7))\n\n\nmain()\n', 'mutated_str_list': "def add(l, v):\n    l.append(v)\n\n\ndef main():\n    m = (1e308 * 10) - (1e308 * 10)\n    t = 0.5\n    for i in range(3):\n        t = t * 1.5 + 0.25\n    names = ['a']\n    alias = names\n    alias.append(m)\n    print(names.count(m), m in names, names == alias)\n    more = ['b']\n    add(more, m)\n    print(more.index(m))\n    grid = [['a'], ['b']]\n    row = grid[0]\n    row.append(m)\n    print(grid[0].count(m), round(t, 3))\n\n\nmain()\n", 'in_tuple_display': "def main():\n    m = (1e308 * 10) - (1e308 * 10)\n    xs = [m, 1.0]\n    print(xs.count(m), m in (m, 1.0), m not in (m, 2.0), m in (1.0, m), float('nan') in (m, 1.0))\n\n\nmain()\n",
 'no_nan_float_free': "def main():\n    words = 'the quick brown fox'.split()\n    names = ['a', 'b', 'c']\n    nums = [3, 1, 2]\n    tot = 0.0\n    x = 1.0\n    for i in range(1000):\n        x = x * 1.0001 + 0.001\n        tot += x\n    print(round(tot, 4), words.count('fox'), 'the' in words, words.index('brown'), names == ['a', 'b', 'c'], nums.count(2), 2 in nums)\n\n\nmain()\n"}

CASES.update({'mix_nan_result': 'def at(l, i):\n    return l[i]\ndef mkn(k):\n    return (k * 1e308) * 10.0 - (k * 1e308) * 10.0\ndef clamp(v, lo, hi):\n    if v < lo:\n        return lo\n    return v\ndef twice(v):\n    return v + v\nn = mkn(1.0)\nxs = [n, 5.0, n]\na = at(xs, 2)\nprint(xs.count(a), xs.index(a), a in xs, a == a, a != a)\nc = clamp(n, 0.0, 1.0)\nprint([c].count(n), [n].count(c), c in [n])\nw = twice(n)\nprint([w].count(w), [w].count(twice(n)), w != w)\nprint(at([1.5, 2.5], 1), clamp(-3.0, 0.0, 1.0), twice(2.25))\nys = [clamp(1.0, 0.0, 2.0), 7.0]\nprint(ys.count(1.0), ys.index(7.0))\n', 'mix_float_function': 'def ident(p): return p\ndef pick(l, i): return l[i]\ndef mk(k):\n    return (k * 1e308) * 10.0 - (k * 1e308) * 10.0\nm = mk(1.0)\nx = ident(m)\nprint([x].count(m))\ny = pick([m, 1.0], 0)\nprint([y].count(y), [y].count(m), y in [m])\nlst = [m, 2.0]\nz = pick(lst, 0)\nprint(lst.count(z), z in lst, lst.index(z))\n', 'mix_attr_dict_item': "class S:\n    def __init__(self, v):\n        self.v = v\ndef ident(p): return p\ndef half(v): return v / 2.0\ndef mk(k):\n    return (k * 1e308) * 10.0 - (k * 1e308) * 10.0\nn = mk(1.0)\ns = S(n)\nt = ident(s.v)\nprint([t].count(n), [s.v].count(t), t in [n])\nd = {'a': n}\nu = ident(d['a'])\nprint([u].count(d['a']), [d['a']].count(u))\nitems = [n, 3.0]\nw = ident(items[0])\nprint(items.count(w), items == [w, 3.0], (w, 1) == (n, 1))\ne = {n: 5}\nprint(e.get(ident(n)), ident(n) in e)\n", 'mix_arg_list_remove': 'def ident(p): return p\ndef scale(a, k): return a * k\ndef first(l): return l[0]\nn = (1e308 * 10) - (1e308 * 10)\nxs = [n, 1.0]\nf = first(xs)\nprint(xs.count(f), xs.index(f), f in xs)\nr = [scale(1.0, 2.0), 4.0]\nprint(r.count(2.0), r.index(4.0), 4.0 in r)\nt = ident(n)\nys = [1.0, t]\nys.remove(n)\nprint(len(ys))\nprint([1.5].count(ident(1.5)))\n'})


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class NanArithmetic(unittest.TestCase):
    def test_cpython_answers(self):
        for name, text in sorted(CASES.items()):
            check_program(self, 'nanar_' + name, text)

    def _stats(self, text):
        with tempfile.TemporaryDirectory(prefix='ail-nanar-') as directory:
            src = Path(directory) / 'p.ail'
            src.write_text(text, encoding='utf-8')
            stats = Path(directory) / 'stats.jsonl'
            env = dict(os.environ, AIL_NO_CACHE='1', AIL_UNIFIED_STATS=str(stats), AIL_QUIET_FALLBACK='1')
            env.pop('AIL_UNIFIED', None)
            env.pop('AIL_UNIFIED_FORCE', None)
            built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', 'p.ail', '--syntax', 'python', '-o', 'exe'],
                                   cwd=directory, capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            return [json.loads(line) for line in stats.read_text(encoding='utf-8').splitlines()][-1]

    def test_floats_stay_boxed_only_when_a_search_may_find_a_float(self):
        # a float local that may be boxed twice is kept boxed one by one (`float_locals_kept_boxed`, the searched
        # lists keep their float elements boxed); when that proof does not apply every float stays boxed
        for name in ('arith_list', 'mutated_str_list', 'dataclass_dict'):
            got = self._stats(CASES[name])
            self.assertFalse(got.get('floats_kept_boxed'), name)
            self.assertTrue(got.get('float_search_site'), name)
            self.assertIn('pf_main:m', got.get('float_locals_kept_boxed'), name)      # the NaN's own name stays boxed
        free = self._stats(CASES['no_nan_float_free'])
        self.assertFalse(free.get('floats_kept_boxed'))
        self.assertFalse(free.get('float_search_site'))
        self.assertGreater(free.get('unboxed_vars', 0), 0)


if __name__ == '__main__':
    unittest.main()
