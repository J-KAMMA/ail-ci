"""cov30: `sorted(d.items())` as a value is compared with CPython 3.12 on both builds.

The key-column lowering used to refuse every `sorted(d.items())` that was not the iterable of
`for k, v in sorted(d.items(), ...)`. The ordinary tuple / dict-view lowering already builds the
list of `(key, value)` tuples exactly, so the refusal is gone: a sorted, reversed or keyed list of
items, sliced, indexed, printed, copied into a dict, returned from a function and reached through
an argument, a list item, an attribute or a dict value now prints what CPython prints on the
general path (`AIL_UNIFIED_FORCE=1`) and on the default build. A kept dict view whose dict changes
is still refused by name, never silently taken as a snapshot.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['basic'] = r'''d = {'pear': 3, 'apple': 1, 'fig': 2, 'kiwi': 1}
print(sorted(d.items()))
print(sorted(d.items(), reverse=True))
print(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))
print(sorted(d.items(), key=lambda kv: kv[1]))
items = sorted(d.items())
print(len(items), items[0], items[-1], items[1:3])
for k, v in items:
    print(k, v)
print(list(sorted(d.items(), key=lambda kv: kv[0].lower())))
print(dict(sorted(d.items())))
'''
PROGRAMS['routes'] = r'''class Holder:
    def __init__(self):
        self.d = {'b': 2, 'a': 1}
def make():
    return {'b': 2, 'a': 1}
def show(d):
    print(sorted(d.items()))
def typed(d: dict[str, int]):
    print(sorted(d.items(), key=lambda kv: kv[1]))
def all_items(d: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(d.items())
show(make())
h = Holder()
show(h.d)
typed(make())
rows = [{'b': 2, 'a': 1}]
print(sorted(rows[0].items()))
lookup = {'k': {'b': 2, 'a': 1}}
print(sorted(lookup['k'].items()))
print(all_items(make()))
'''
PROGRAMS['types'] = r'''print(sorted({}.items()))
print(sorted({5: 'x'}.items()))
print(sorted({-3: 'x', 2: 'y', 0: 'z'}.items()))
print(sorted({True: 't', False: 'f'}.items()))
a: dict[str, float] = {'b': 2.5, 'a': -1.5, 'c': 0.0}
print(sorted(a.items()))
print(sorted(a.items(), key=lambda kv: abs(kv[1])))
b: dict[str, bool] = {'b': True, 'a': False}
print(sorted(b.items()))
c: dict[str, list[int]] = {'b': [2], 'a': [1]}
print(sorted(c.items()))
d: dict[str, tuple[int, str]] = {'b': (2, 'y'), 'a': (1, 'x')}
print(sorted(d.items()))
print(sorted(d.items(), key=lambda kv: kv[1][0]))
e: dict[tuple[int, str], int] = {(2, 'b'): 1, (1, 'a'): 2}
print(sorted(e.items()))
f = {'bb': 2 ** 40, 'a': -(2 ** 40), 'cc': 2 ** 62}
print(sorted(f.items()))
print(sorted(f.items(), key=lambda kv: -kv[1]))
'''
PROGRAMS['mutation'] = r'''d = {'b': 2, 'a': 1}
items = sorted(d.items())
d['c'] = 3
d['a'] = 99
print(items)
print(sorted(d.items()))
def key(kv):
    d[kv[0] + 'x'] = kv[1] + 10
    return kv[1]
print(sorted(d.items(), key=key))
print(d)
'''
PROGRAMS['objects'] = r'''class Box:
    def __init__(self, n):
        self.n = n
    def __repr__(self):
        return 'B' + str(self.n)
d = {'b': Box(2), 'a': Box(1)}
print(sorted(d.items()))
print(sorted(d.items(), key=lambda kv: kv[1].n))
print(sorted(d.items(), reverse=True))
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)


class Refused(unittest.TestCase):
    def refused(self, text, fragment, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(fragment, built.stdout + built.stderr)

    def test_kept_dict_view(self):
        source = ("d = {'b': 2, 'a': 1}\nxs = d.items()\nd['c'] = 3\nprint(list(xs))\n")
        self.refused(source, "dict view kept", AIL_UNIFIED_FORCE="1")
        self.refused(source, "dict view kept")


if __name__ == "__main__":
    unittest.main()
