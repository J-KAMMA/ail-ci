"""Silent differences found by the fuzz4 round over dicts, sets and comprehensions.

1. A dict operation that takes a key from its own entries (or probes one once) must not call
   ``__hash__`` again.  CPython hashes once for ``pop``/``setdefault`` (hit or miss), and never
   for ``dict.copy``, ``dict.update(other_dict)``, ``dict(other_dict)`` or ``popitem``: those
   reuse the stored hash.  The object runtime used ``get`` then ``del``/``set`` and re-hashed
   keys in ``update``/``copy``/``dict``/``popitem``, so a user ``__hash__`` with a side effect
   printed extra lines (and could take a different branch on the second call).

2. CPython 3.12's ``BUILD_MAP``/``BUILD_SET`` evaluate every key/value/element expression
   before hashing any of them.  A dict literal ``{[1]: f(), "b": g()}`` therefore runs ``g()``
   and only then raises TypeError, and a two-entry literal with a user ``__hash__`` runs both
   values before both hashes.  AIL hashed and inserted each pair as soon as it was built, so
   the later expressions were skipped.

Both are checked against CPython 3.12, with the general path forced and with the default build
(the typed path refuses user __hash__ keys and falls back to the general path, so both builds
run the same object runtime here).  stdout and the exit status must match.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


HASH_METHODS = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H")
        return self.v % 4
    def __eq__(self, other):
        print("E")
        return self.v == other.v


def main():
    a = K(1)
    b = K(2)
    q = K(3)
    d = {a: 10, b: 20}
    print(d.get(a))
    print(d.get(q, -1))
    print(d.pop(a))
    print(d.pop(q, -2))
    print(d.pop(b, -3))
    print(d.setdefault(b, 99))
    print(d.setdefault(q, 33))
    print(a in d, b in d, q in d)
    d[a] = 5
    d[b] = 6
    d.update({a: 7})
    e = d.copy()
    d.update(e)
    f = dict(d)
    print(len(d), len(e), len(f))
    f.popitem()
    print(len(f))
    print(sorted(d.values()), sorted(e.values()), sorted(f.values()))


main()
'''


HASH_EMPTY_COPY = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H", self.v)
        return 1
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def main():
    k = K(9)
    empty = {}
    print(empty.pop(k, -1))
    try:
        empty.pop(k)
    except KeyError:
        print("empty")
    d = {}
    for i in range(3):
        d[K(i)] = i
    c = d.copy()
    print(len(c))
    c.popitem()
    print(len(c))
    d.update(c)
    print(len(d))


main()
'''


LITERAL_ORDER = r'''class H:
    def __hash__(self):
        print("H")
        return 1


def mark(x):
    print("m", x)
    return x


def main():
    try:
        d = {[1]: mark(10), "b": mark(20)}
        print(len(d))
    except TypeError:
        print("typeerror")
    try:
        s = {[1], mark(3)}
        print(len(s))
    except TypeError:
        print("settypeerror")
    e = {H(): mark(4), H(): mark(5)}
    print(len(e))
    f = {H(), H()}
    print(len(f))
    g = {"a": mark(6), "b": mark(7)}
    print(sorted(g.items()))


main()
'''


class Fuzz4Tests(unittest.TestCase):
    def run_cpython(self, directory, text):
        src = Path(directory) / 'cpython_main.py'
        src.write_text(text, encoding='utf-8')
        done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                              env=dict(os.environ, PYTHONUTF8='1'))
        return done.stdout, done.returncode

    def build(self, directory, text, general):
        src = Path(directory) / 'main.py'
        src.write_text(text, encoding='utf-8')
        exe = Path(directory) / ('exe_' + ('g' if general else 'd'))
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
        env.pop('AIL_NO_GENERAL', None)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        return subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                               '-o', exe.name], cwd=directory, capture_output=True, text=True,
                              timeout=900, env=env), exe

    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz4-') as directory:
            want_out, want_rc = self.run_cpython(directory, text)
            for general in (True, False):
                built, exe = self.build(directory, text, general)
                self.assertEqual(built.returncode, 0, '%s %s build: %s' %
                                 (name, 'general' if general else 'default',
                                  (built.stdout + built.stderr)[-1500:]))
                done = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(done.stdout.decode('utf-8', 'replace'), want_out.decode('utf-8', 'replace'),
                                 '%s %s stdout' % (name, 'general' if general else 'default'))
                self.assertEqual(done.returncode, want_rc,
                                 '%s %s exit' % (name, 'general' if general else 'default'))

    def test_dict_operations_hash_the_key_once(self):
        self.check('hash-methods', HASH_METHODS)

    def test_empty_pop_copy_and_popitem_do_not_rehash(self):
        self.check('hash-empty-copy', HASH_EMPTY_COPY)

    def test_dict_and_set_literals_evaluate_before_hashing(self):
        self.check('literal-order', LITERAL_ORDER)


if __name__ == '__main__':
    unittest.main()
