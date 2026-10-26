"""pre57: dict delete/reinsert keeps CPython's key-table shape.

The pre43 reviewer recorded that ``update`` and ``dict()`` after a delete/reinsert still
called a user ``__eq__`` a different number of times from CPython 3.12 (p14 omitted
``E 20 11``), and that constructing a source dict after delete+insert could print
``__eq__`` calls in a different order.  AIL rebuilt the whole index after every delete;
CPython leaves a dummy index slot and keeps ``dk_nentries``.  Both builds now track the
entry count, trailing dummies and dummy index slots, so later inserts probe in CPython's
order, and a dict comparison skips those dummies instead of reading ``index[-2]``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


UPDATE_DELETE_REINSERT = r'''class K:
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


class Holder:
    def __init__(self, d):
        self.d = d


def via(x):
    return dict(x)


def main():
    d = build(21)
    del d[K(1)]
    d[K(20)] = 20
    del d[K(5)]
    d[K(21)] = 21
    del d[K(21)]
    print("-- source", [k.v for k in d])
    print("-- dict(d)")
    e = dict(d)
    print(len(e), [k.v for k in e])
    print("-- copy")
    c = d.copy()
    print(len(c), [k.v for k in c])
    print("-- update empty")
    u = {}
    u.update(d)
    print(len(u), [k.v for k in u])
    print("-- via argument", len(via(d)))
    print("-- via list item", len(dict([d][0])))
    h = Holder(d)
    print("-- via attribute", len(dict(h.d)))
    box = {"x": d}
    print("-- via dict value", len(dict(box["x"])))
    print("-- self update")
    d.update(d)
    print(len(d))
    print("-- update nonempty")
    w = {K(99): 99}
    w.update(d)
    print(len(w), [k.v for k in w])


main()
'''


TAIL_POP_REINSERT = r'''class K:
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
    print(sorted(k.v for k in dict(c)))

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


EQ_TOMBSTONE = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
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
    x = build(6)
    y = build(6)
    del y[K(3)]
    print("one removed", x == y, y == x)
    del x[K(3)]
    print("both removed", x == y, y == x)
    del y[K(0)]
    del x[K(0)]
    print("two removed", x == y, y == x)
    z = build(6)
    del z[K(1)]
    z[K(6)] = 6
    del z[K(0)]
    print("different content", z == build(6), build(6) == z)
    print("keys", [k.v for k in z])
    e = dict(z)
    print("dict", e == z, z == e)
    u = {}
    u.update(z)
    print("update", u == z, z == u)


main()
'''


SOURCE_ORDER = r'''class K:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        return 0
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def main():
    d = {}
    for i in range(20):
        d[K(i)] = i
    del d[K(0)]
    d[K(20)] = 20
    del d[K(5)]
    d[K(21)] = 21
    del d[K(21)]
    print("keys", [k.v for k in d])
    print("dict keys", [k.v for k in dict(d)])
    print("copy keys", [k.v for k in d.copy()])
    u = {}
    u.update(d)
    print("update keys", [k.v for k in u])


main()
'''


PLAIN_BOUNDARIES = r'''def main():
    e = {}
    print(len(dict(e)), len(e.copy()), len(e))
    e.update({})
    print(len(e))
    d = {}
    for i in range(-3, 4):
        d[i] = i * i
    print(sorted(d.items()))
    del d[-3]
    del d[3]
    print(sorted(dict(d).items()), sorted(d.copy().items()))
    u = {}
    u.update(d)
    print(sorted(u.items()))
    print(d.popitem(), sorted(d.items()))
    d.clear()
    print(len(d), len(dict(d)), len(d.copy()))
    s = {"a": 1, "b": 2}
    t = {}
    t.update(s)
    print(sorted(t.items()))
    del s["a"]
    print(sorted(dict(s).items()), sorted(s.copy().items()))
    s["c"] = 3
    del s["c"]
    print(sorted(dict(s).items()))


main()
'''


REG_EQ_REINSERT_ORDER = r'''class K:
    def __init__(self, v, h):
        self.v = v
        self.h = h
    def __hash__(self):
        return self.h
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def main():
    d = {}
    for i in range(6):
        d[K(i, (i * 32) % 64)] = i
    for i in (0, 2, 4):
        del d[K(i, (i * 32) % 64)]
    for j in range(3):
        d[K(1000 + j, ((1000 + j) * 32) % 64)] = 1000 + j
    print("keys", [k.v for k in d])
    e = dict(d)
    print("ekeys", [k.v for k in e])
    print("d==e")
    print(d == e)
    print("e==d")
    print(e == d)


main()
'''


REG_POPITEM_USABLE = r'''class K:
    def __init__(self, v, h):
        self.v = v
        self.h = h
    def __hash__(self):
        return self.h
    def __eq__(self, other):
        print("E", self.v, other.v)
        return self.v == other.v


def main():
    d = {}
    for i in range(21):
        d[K(i, (i * 3) % 64)] = i
    d.popitem()
    d.popitem()
    d[K(2000, (2000 * 3) % 64)] = 2000
    print("keys", [k.v for k in d])
    print("-- dict")
    e = dict(d)
    print("ekeys", [k.v for k in e])


main()
'''


class Pre57Tests(unittest.TestCase):
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
        with tempfile.TemporaryDirectory(prefix='ail-pre57-') as directory:
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

    def test_update_and_dict_after_delete_reinsert(self):
        self.check('update-delete-reinsert', UPDATE_DELETE_REINSERT)

    def test_tail_dummies_and_popitem(self):
        self.check('tail-pop-reinsert', TAIL_POP_REINSERT)

    def test_dict_equality_skips_dummy_index_slots(self):
        self.check('eq-tombstone', EQ_TOMBSTONE)

    def test_source_construction_order_after_delete_reinsert(self):
        self.check('source-order', SOURCE_ORDER)

    def test_empty_negative_and_plain_boundaries(self):
        self.check('plain-boundaries', PLAIN_BOUNDARIES)

    def test_equality_order_after_delete_reinsert(self):
        self.check('reg-eq-reinsert-order', REG_EQ_REINSERT_ORDER)

    def test_popitem_does_not_restore_usable(self):
        self.check('reg-popitem-usable', REG_POPITEM_USABLE)


if __name__ == '__main__':
    unittest.main()
