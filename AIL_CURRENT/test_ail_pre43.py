"""pre43: dict(d), update and copy use CPython's stored hashes and key-table sharing.

CPython's ``dict(d)`` (and ``d.copy()``) into an empty target shares a clean source's key
table, so a user ``__hash__`` / ``__eq__`` is not called at all.  A source that has had a
deletion (CPython's table then holds a dummy slot) is inserted in order with its stored hash:
``__hash__`` is still not called, and ``__eq__`` runs only for a real collision.  AIL hashed
and compared every key in both cases.  ``update`` follows the same rule when its target is
empty, and ``d.update(d)`` is a no-op.  Both builds are compared with CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


CLEAN = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H", self.v)
        return self.v % 4
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def build(n):
    d = {}
    for i in range(n):
        d[K(i)] = i
    return d


class Holder:
    def __init__(self, d):
        self.d = d


def via(x):
    return dict(x)


def main():
    for n in (0, 1, 4, 5, 16):
        d = build(n)
        print("--", n)
        e = dict(d)
        print(len(e), [k.v for k in e])
    d = build(5)
    print("arg", len(via(d)))
    box = [build(5)]
    print("list", len(dict(box[0])))
    h = Holder(build(5))
    print("attr", len(dict(h.d)))
    m = {"x": build(5)}
    print("dict value", len(dict(m["x"])))


main()
'''


DIRTY = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H", self.v)
        return self.v % 3
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def build(n):
    d = {}
    keys = []
    for i in range(n):
        k = K(i)
        keys.append(k)
        d[k] = i
    return d, keys


def main():
    d, keys = build(5)
    del d[keys[1]]
    print("-- dict(d)")
    e = dict(d)
    print(len(e), [k.v for k in e])
    print("-- copy")
    c = d.copy()
    print(len(c), [k.v for k in c])
    print("-- dict(copy)")
    print(len(dict(c)))
    print("-- update empty")
    u = {}
    u.update(d)
    print(len(u), [k.v for k in u])
    print("-- update nonempty")
    w = {K(99): 99}
    w.update(d)
    print(len(w), [k.v for k in w])
    print("-- update self")
    d.update(d)
    print(len(d))


main()
'''


UPDATE = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H", self.v)
        return self.v % 2
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def main():
    for n in (0, 1, 3, 6):
        d = {}
        for i in range(n):
            d[K(i)] = i
        print("--", n)
        u = {}
        u.update(d)
        print("empty", len(u), [k.v for k in u])
        w = {K(50): 50}
        w.update(d)
        print("nonempty", len(w))
        c = d.copy()
        print("copy", len(c))
        f = dict(d)
        print("dict", len(f))
        d.update(d)
        print("self", len(d))


main()
'''


CAPACITY = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        return self.v % 3
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def make(n):
    d = {}
    keys = []
    for i in range(n):
        k = K(i)
        keys.append(k)
        d[k] = i
    return d, keys


def main():
    d, keys = make(5)
    del d[keys[1]]
    u = {}
    u.update(d)
    u[K(44)] = 44
    print("update insert", len(u), [k.v for k in dict(u)])

    d, keys = make(12)
    for i in range(7):
        del d[keys[i]]
    c = d.copy()
    print("copy many dead", len(c), [k.v for k in dict(c)])

    d, keys = make(8)
    del d[keys[7]]
    d.popitem()
    print("del last popitem", [k.v for k in dict(d)])
    c = d.copy()
    print("copy", [k.v for k in dict(c)])

    d, keys = make(20)
    d.clear()
    for i in range(1, 7):
        d[K(i)] = i
    print("clear refill", [k.v for k in dict(d)])
    c = d.copy()
    print("copy", [k.v for k in dict(c)])


main()
'''


NONUSER = r'''def build(n):
    d = {}
    for i in range(n):
        d[-i] = i
    return d


def main():
    d = build(6)
    print(len(dict(d)), sorted(dict(d).items()))
    e = {}
    e.update(d)
    print(len(e), sorted(e.items()))
    c = d.copy()
    c[-1] = 99
    print(sorted(c.items()))
    del d[-2]
    print(len(dict(d)), sorted(dict(d).keys()))
    empty = {}
    print(len(dict(empty)), len(empty.copy()))
    s = {"a": 1, "b": 2}
    t = {}
    t.update(s)
    print(sorted(t.items()))
    print(len(dict({})), len(dict({"x": 7})))


main()
'''


TAILGAP = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        print("H", self.v)
        return 0
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def build(n):
    d = {}
    for i in range(n):
        d[K(i)] = i
    return d


def main():
    d = build(4)
    del d[K(3)]
    d[K(9)] = 9
    del d[K(9)]
    print("-- popitem", d.popitem()[0].v)
    c = d.copy()
    print("-- dict(c)")
    e = dict(c)
    print(sorted(k.v for k in e))

    d = build(4)
    del d[K(1)]
    del d[K(3)]
    print("-- middle and tail", [k.v for k in d])
    print("-- popitem 2", d.popitem()[0].v)
    c = d.copy()
    print("-- copy", [k.v for k in c])
    print("-- dict(copy)", [k.v for k in dict(c)])
    u = {}
    u.update(c)
    print("-- update", [k.v for k in u])

    d = build(6)
    for i in (5, 4, 3):
        del d[K(i)]
        d[K(100 + i)] = 100 + i
        del d[K(100 + i)]
    print("-- tail cycles", [k.v for k in d])
    print("-- copy", [k.v for k in d.copy()])
    print("-- dict", [k.v for k in dict(d)])
    print("-- pop", d.popitem()[0].v)
    print("-- final", [k.v for k in dict(d)])


main()
'''


class Pre43Tests(unittest.TestCase):
    def run_cpython(self, directory, text):
        src = Path(directory) / 'cpython_main.py'
        src.write_text(text, encoding='utf-8')
        done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=180,
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
        with tempfile.TemporaryDirectory(prefix='ail-pre43-') as directory:
            want_out, want_rc = self.run_cpython(directory, text)
            for general in (True, False):
                built, exe = self.build(directory, text, general)
                self.assertEqual(built.returncode, 0, '%s %s build: %s' %
                                 (name, 'general' if general else 'default',
                                  (built.stdout + built.stderr)[-1500:]))
                done = subprocess.run([str(exe)], capture_output=True, timeout=180, cwd=directory)
                self.assertEqual(done.stdout.decode('utf-8', 'replace'), want_out.decode('utf-8', 'replace'),
                                 '%s %s stdout' % (name, 'general' if general else 'default'))
                self.assertEqual(done.returncode, want_rc,
                                 '%s %s exit' % (name, 'general' if general else 'default'))

    def test_clean_source_is_copied_without_hashing(self):
        self.check('clean', CLEAN)

    def test_dirty_source_uses_stored_hashes(self):
        self.check('dirty', DIRTY)

    def test_update_and_copy_call_counts(self):
        self.check('update', UPDATE)

    def test_plain_keys_are_unchanged(self):
        self.check('nonuser', NONUSER)

    def test_table_shape_after_update_copy_popitem_clear(self):
        self.check('capacity', CAPACITY)

    def test_trailing_dummies_after_delete_reinsert_popitem(self):
        self.check('tailgap', TAILGAP)


if __name__ == '__main__':
    unittest.main()
