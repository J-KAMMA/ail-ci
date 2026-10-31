"""Branch cov19: `sorted(d.items())` as a value matches CPython 3.12 on both builds.

The ordinary emitter already builds a dict's `.items()` sort as a list of AIL tuples -- exactly
the values CPython's `dict_items` iterates -- so indexing, tuple unpacking, `dict(...)` and the
repr all agree.  The key-column sort rewrite in sortkeys.py runs only after the ordinary compile
fails; it used to refuse every `sorted(d.items())` as a value even when an unrelated statement in
the program was the real blocker.  It now leaves that call to the ordinary path.

* PROGRAMS are compiled twice (AIL_UNIFIED_FORCE=1, the general path; and the default build, which
  falls back to it) and must print what CPython prints;
* the rewrite itself must not raise for `sorted(d.items())` (the regression that used to hide the
  true refusal), while a keyed list sort still rewrites;
* a dict subclass (a construct that cannot be matched) stays a named refusal.
"""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import sortkeys

PROGRAMS = {}
PROGRAMS['value'] = r'''d = {"b": 2, "a": 1, "c": 3}
r = sorted(d.items())
print(r)
print(len(r), r[0], r[0][0], r[0][1], r[-1])
for k, v in r:
    print(k, v)
print(dict(r))
print(sorted(d.items(), reverse=True))
print(dict(sorted({"x": 9}.items())))
'''
PROGRAMS['key'] = r'''d = {"b": 2, "a": 1, "c": 3}
r = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
print(r)
print(dict(r))
for k, v in r[:2]:
    print(k, v)
print(sorted(d.items(), key=len))
print(sorted(d.items(), key=lambda kv: kv[1], reverse=True))
'''
PROGRAMS['routes'] = r'''def show(pairs):
    return sorted(pairs)

class Box:
    def __init__(self, d):
        self.d = d

def make():
    return {"z": 3, "y": 2}

items = [{"b": 2, "a": 1}]
values = {"k": {"d": 4, "c": 5}}
b = Box({"n": 7, "m": 6})
print(show(items[0].items()))
print(sorted(values["k"].items()))
print(sorted(b.d.items()))
print(sorted(make().items()))
alias = b.d
print(sorted(alias.items()))
print(sorted({}.items()))
'''
PROGRAMS['negative_int_keys'] = r'''d = {3: "c", -1: "a", 2: "b"}
print(sorted(d.items()))
print(sorted(d.items(), key=lambda kv: -kv[0]))
print(dict(sorted(d.items(), reverse=True)))
r = sorted(d.items())
r.append((0, "z"))
print(r)
for k, v in sorted(d.items(), key=lambda kv: abs(kv[0])):
    print(k, v)
'''
PROGRAMS['snapshot'] = r'''d = {"b": 2, "a": 1}
r = sorted(d.items())
d["c"] = 3
del d["a"]
print(r)
print(sorted(d.items()))
'''

REFUSED = r'''class D(dict[str, int]):
    pass

d: D = D()
d["a"] = 1
print(sorted(d.items()))
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
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


class Rewrite(unittest.TestCase):
    def test_items_value_is_not_refused(self):
        tree = ast.parse('def f():\n    d = {"a": 1}\n    return sorted(d.items())\n')
        self.assertEqual(sortkeys.rewrite(tree, 1, lambda key: False, Exception), 0)

    def test_keyed_list_sort_still_rewrites(self):
        tree = ast.parse('def f():\n    xs = [3, 1, 2]\n    return sorted(xs, key=lambda x: -x)\n')
        self.assertEqual(sortkeys.rewrite(tree, 1, lambda key: False, Exception), 1)


class Refused(unittest.TestCase):
    def test_dict_subclass_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, REFUSED, "r", AIL_UNIFIED_FORCE="1")
            self.assertNotEqual(built.returncode, 0)
            message = built.stdout + built.stderr
            self.assertIn("non-name base class", message)
            self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main()
