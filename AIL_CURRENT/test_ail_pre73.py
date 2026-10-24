"""pre73: dict key-table shape and probing for user-hash keys.

The pre57 reviewer recorded a pre-existing difference: a fuzz scenario
``n=10,hmul=32,every,update0`` (ten keys whose ``__hash__`` is
``(v * 32) % 64``, every key deleted and reinserted, no ``update``) printed a
different number of user ``__eq__`` calls and a different checksum on both
builds.  AIL kept a compact insertion-order index, rehashed on every delete and
reinserted merge/copy sources with a fresh ``__hash__`` call; CPython 3.12
leaves a dummy index slot, tracks ``dk_nentries``/``dk_usable``, probes with
the perturbed sequence and copies a dict source with its stored hashes.

Both builds now follow that shape.  The programs below compare with CPython:
the recorded scenario, popitem/reinsert, numeric boundaries and the source
reaching ``dict()`` through an argument, a list item, an attribute and a dict
value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


SCENARIO = r'''HC = [0]
EC = [0]
CS = [0]


class K:
    def __init__(self, v: int) -> None:
        self.v = v
    def __hash__(self) -> int:
        HC[0] = HC[0] + 1
        return (self.v * 32) % 64
    def __eq__(self, other) -> bool:
        EC[0] = EC[0] + 1
        CS[0] = (CS[0] * 31 + (self.v + 7) * 131 + (other.v + 11) * 17) % 1000000007
        return self.v == other.v


def main() -> None:
    d = {}
    for i in range(10):
        d[K(i)] = i
    for i in range(10):
        del d[K(i)]
        d[K(i)] = i * 10
    print("A", HC[0], EC[0], CS[0])
    e = dict(d)
    print("B", HC[0], EC[0], CS[0])
    c = d.copy()
    print("C", HC[0], EC[0], CS[0])
    print("EQ", d == e, e == d, HC[0], EC[0], CS[0])
    k, v = d.popitem()
    print("P", k.v, v, HC[0], EC[0], CS[0])
    print("KEYS", [x.v for x in d])
    u = {}
    u.update(d)
    print("U", HC[0], EC[0], CS[0], [x.v for x in u])


main()
'''


POP_REINSERT = r'''class K:
    def __init__(self, v: int) -> None:
        self.v = v
    def __hash__(self) -> int:
        print("H", self.v)
        return (self.v * 32) % 64
    def __eq__(self, other) -> bool:
        print("E", self.v, other.v)
        return self.v == other.v


def main() -> None:
    d = {}
    for i in range(10):
        d[K(i)] = i
        k, v = d.popitem()
        d[K(v)] = v
    print("KEYS", [x.v for x in d])
    print("DICT", [x.v for x in dict(d)])
    print("COPY", [x.v for x in d.copy()])
    print("EQ", d == dict(d))


main()
'''


BOUNDARIES = r'''class H:
    def __init__(self, v: int, h: int) -> None:
        self.v = v
        self.h = h
    def __hash__(self) -> int:
        print("H", self.v)
        return self.h
    def __eq__(self, other) -> bool:
        print("E", self.v, other.v)
        return self.v == other.v


def main() -> None:
    e = {}
    print("empty", len(e), len(dict(e)), len(e.copy()))
    e.update({})
    print("update-empty", len(e))
    d = {}
    for i in range(-3, 4):
        d[i] = i * i
    print("ints", [d[k] for k in range(-3, 4)])
    del d[-3]
    del d[3]
    d[-3] = 9
    d[3] = 9
    print("reinsert", [d[k] for k in range(-3, 4)])
    h = {}
    for v, hv in [(1, -1), (2, -2), (3, 0), (4, 2 ** 31), (5, -(2 ** 62))]:
        h[H(v, hv)] = v
    print("hashes", [h[H(v, hv)] for v, hv in [(1, -1), (2, -2), (3, 0), (4, 2 ** 31), (5, -(2 ** 62))]])
    for v, hv in [(1, -1), (3, 0)]:
        del h[H(v, hv)]
    for v, hv in [(6, -1), (7, 0)]:
        h[H(v, hv)] = v
    print("dirty", [x.v for x in h])
    print("copy", [x.v for x in h.copy()])
    print("dict", [x.v for x in dict(h)])
    print("eq", h == dict(h), dict(h) == h)
    h.clear()
    print("cleared", len(h), len(dict(h)))
    h[H(8, 0)] = 8
    print("reuse", [x.v for x in h], h[H(8, 0)])


main()
'''


ALIAS = r'''class K:
    def __init__(self, v: int) -> None:
        self.v = v
    def __hash__(self) -> int:
        return (self.v * 32) % 64
    def __eq__(self, other) -> bool:
        print("E", self.v, other.v)
        return self.v == other.v


class Box:
    def __init__(self, d) -> None:
        self.d = d


def take(d) -> int:
    return len(dict(d))


def main() -> None:
    d = {}
    for i in range(10):
        d[K(i)] = i
    for i in range(0, 10, 2):
        del d[K(i)]
        d[K(i)] = i * 2
    items = [d]
    box = Box(d)
    vals = {"x": d}
    print("arg", take(d))
    print("item", len(dict(items[0])))
    print("attr", len(dict(box.d)))
    print("value", len(dict(vals["x"])))
    c = d.copy()
    d[K(50)] = 50
    print("indep", len(c), len(d), len(dict(c)))
    u = {}
    u[K(99)] = 99
    u.update(d)
    print("upd", len(u), [x.v for x in u])
    d.update(d)
    print("self", len(d))


main()
'''


SIZES = r'''class KK:
    def __init__(self, v: int, h: int) -> None:
        self.v = v
        self.h = h
    def __hash__(self) -> int:
        return self.h
    def __eq__(self, other) -> bool:
        print("Q", self.v, other.v)
        return self.v == other.v


def run(n: int, mul: int) -> None:
    d = {}
    for i in range(n):
        d[KK(i, (i * mul) % 64)] = i
    for i in range(0, n, 2):
        del d[KK(i, (i * mul) % 64)]
    for i in range(0, n, 2):
        d[KK(i, (i * mul) % 64)] = i + 100
    print("K", n, mul, [x.v for x in d])
    print("D", [x.v for x in dict(d)])
    print("C", [x.v for x in d.copy()])
    print("E", d == dict(d), dict(d) == d)


def main() -> None:
    for n in range(0, 17):
        run(n, 32)
    for n in (5, 10, 21):
        run(n, 3)


main()
'''


class Pre73Tests(unittest.TestCase):
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
        with tempfile.TemporaryDirectory(prefix='ail-pre73-') as directory:
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

    def test_user_hash_delete_reinsert_scenario(self):
        self.check('scenario', SCENARIO)

    def test_popitem_reinsert(self):
        self.check('pop-reinsert', POP_REINSERT)

    def test_numeric_and_hash_boundaries(self):
        self.check('boundaries', BOUNDARIES)

    def test_source_reaches_dict_through_containers(self):
        self.check('alias', ALIAS)

    def test_sizes_and_hash_schemes(self):
        self.check('sizes', SIZES)


if __name__ == '__main__':
    unittest.main()
