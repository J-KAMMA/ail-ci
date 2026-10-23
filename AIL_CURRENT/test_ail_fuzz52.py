"""Differential round 52: frozenset hashing and numeric key collisions.

Found with small programs compared against CPython on both builds:

`hash(frozenset(...))` used the set table's private element hash and missed CPython's
frozenset_hash details (the element's Python hash, -1 mapped to -2, and a final -1 mapped
to 590923713). `hash(frozenset({1}))` and `hash(frozenset({1.0}))` printed a value unrelated
to CPython's; the general form below now matches CPython, so equal frozensets (1 / 1.0 /
True elements) agree on both the value and the collision.

The programs also keep the surrounding behaviour compared on both builds: mixed int, float
and bool keys and memberships, tuples and frozensets as dict keys, nested containers, empty,
zero, negative and huge keys, and values reaching the code through an argument, a list item,
an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FROZENSET_HASH = r'''def show(x):
    print(hash(x))


def main():
    print(hash(frozenset()))
    print(hash(frozenset({1})))
    print(hash(frozenset({0})))
    print(hash(frozenset({-1})))
    print(hash(frozenset({1, 0})))
    print(hash(frozenset({1.0, 2.0})))
    print(hash(frozenset({True, 2})))
    print(hash(frozenset({1000000000000})))
    print(hash(frozenset({-1000000000000})))
    print(hash(frozenset({1.5})))
    print(hash(frozenset({(1, 2)})))
    print(hash(frozenset({(1.0, 2.0)})))
    print(hash(frozenset({frozenset({1})})))
    print(hash(frozenset({frozenset()})))
    print(hash(frozenset({1})) == hash(frozenset({1.0})) == hash(frozenset({True})))
    show(frozenset({3}))


main()
'''

FROZENSET_HASH_CONTAINERS = r'''class Box:
    def __init__(self):
        self.f = frozenset({(1, 2)})
        self.g = frozenset({4})


def main():
    xs = [frozenset({(1, 2)}), frozenset({4})]
    d = {"a": frozenset({(1, 2)}), "b": frozenset({5})}
    b = Box()
    print(hash(xs[0]), hash(xs[1]))
    print(hash(d["a"]), hash(d["b"]))
    print(hash(b.f), hash(b.g))
    print(hash(frozenset({(1, 2)})) == hash(frozenset({(1.0, 2.0)})))


main()
'''

NUMERIC_KEYS = r'''def main():
    d = {1: "a"}
    d[1.0] = "b"
    d[True] = "c"
    print(len(d), d, d[1], d[1.0], d[True])
    print(1 in d, 1.0 in d, True in d, False in d, 0 in d)
    s = {1, 2, 3}
    print(len(s), True in s, 1.0 in s, 2.0 in s, 4.0 in s, False in s, 0.0 in s)
    s2 = {1.0}
    s2.add(1)
    s2.add(True)
    print(len(s2), [x for x in s2])
    vals = [0, -0.0, 0.0, False, 1, 1.0, True, -1, -1.0, 1000000000000, 1000000000000.0]
    e = {}
    for i, k in enumerate(vals):
        e[k] = e.get(k, 0) + 1
    print(len(e), sum(e[k] for k in vals))
    for k in vals:
        print(k in e, e[k])


main()
'''

FROZEN_AND_TUPLE_KEYS = r'''def main():
    d = {(1, 2): "a", (1.0, 2.0): "b"}
    print(len(d), d[(1, 2)], d[(True, 2)], (1.0, 2) in d)
    d[(1, 2.0)] = "c"
    print(len(d), d)
    fs = frozenset({(1, 2), (1.0, 2.0), (True, 2)})
    d2 = {fs: "x"}
    print(len(fs), d2[frozenset({(1, 2)})], d2[frozenset({(True, 2.0)})])
    d2[frozenset({(1, 2)})] = "y"
    print(len(d2), d2[fs])
    print(frozenset() in {frozenset(): 1}, frozenset() in {frozenset({1}): 1})
    nested = {(1, (2, frozenset({3, 4}))): "n"}
    k = (1.0, (2.0, frozenset({3.0, 4.0})))
    print(len(nested), k in nested, nested[k])


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


class Fuzz52Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz52-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_frozenset_hash(self):
        self.check('frozenset_hash', FROZENSET_HASH)

    def test_frozenset_hash_through_containers(self):
        self.check('frozenset_hash_containers', FROZENSET_HASH_CONTAINERS)

    def test_numeric_key_collisions(self):
        self.check('numeric_keys', NUMERIC_KEYS)

    def test_frozenset_and_tuple_keys(self):
        self.check('frozen_tuple_keys', FROZEN_AND_TUPLE_KEYS)


if __name__ == '__main__':
    unittest.main()
