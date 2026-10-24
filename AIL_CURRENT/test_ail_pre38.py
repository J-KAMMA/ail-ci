"""CPython's mapping protocol in dict(<user instance>) -- pre-existing difference q01/q07 of job pre25.

`dict(D())` where D has a `keys` method (or a `keys` class / instance attribute) takes
CPython's MAPPING protocol: call keys(), then map every key through D.__getitem__.  It only
falls back to the pair-sequence path when there is no keys attribute.  A keys() result that
cannot be iterated is CPython's "<D>.keys() returned a non-iterable (type <X>)", and a keys
attribute that is not callable is "'<type>' object is not callable".  Iterating an instance
without __iter__ names its class ("'D' object is not iterable"), not "instance".
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MAPPING = r'''class D:
    def __init__(self):
        self.tag = 10
    def keys(self):
        return ["a", "bb"]
    def __getitem__(self, k):
        return self.tag + len(k)
class Holder:
    def __init__(self):
        self.d = D()
class FuncKeys:
    keys = lambda self: ["q"]
    def __getitem__(self, k):
        return 7
class Both:
    def keys(self):
        return ["a"]
    def __getitem__(self, k):
        return 9
    def __iter__(self):
        return iter([("z", 0)])
class Pairs:
    def __iter__(self):
        return iter([("a", 1), ("b", 2)])
def make() -> D:
    return D()
def via(x):
    return dict(x)
def main() -> None:
    d = D()
    print(dict(d))
    print(dict(make()))
    print(via(d))
    xs = [d]
    print(dict(xs[0]))
    h = Holder()
    print(dict(h.d))
    box = {"k": d}
    print(dict(box["k"]))
    print(dict(FuncKeys()))
    print(dict(Both()), list(Both()))
    print(dict(Pairs()), list(Pairs()))
main()
'''

FAILURES_CAUGHT = r'''class NoIter:
    def __init__(self):
        self.v = 1
class BadKeys:
    def keys(self):
        return NoIter()
class ListKeys:
    keys = [["a", 1]]
class StrKeys:
    keys = "ab"
class InstanceKeys:
    def __init__(self):
        self.keys = [["x", 2]]
class NoKeys:
    def __init__(self):
        self.v = 1
class MissingGetitem:
    def keys(self):
        return ["a"]
class EmptyKeys:
    def keys(self):
        return []
class RaisesKey:
    def keys(self):
        return ["x"]
    def __getitem__(self, k):
        raise KeyError(k)
def via(x):
    return dict(x)
def main() -> None:
    for src in (BadKeys(), ListKeys(), StrKeys(), InstanceKeys(), NoKeys(), MissingGetitem()):
        try:
            print(dict(src))
        except (TypeError, KeyError) as e:
            print(type(e).__name__, e)
        try:
            print(via(src))
        except (TypeError, KeyError) as e:
            print(type(e).__name__, e)
    try:
        print(dict([NoKeys()][0]))
    except TypeError as e:
        print("TypeError", e)
    try:
        print(dict({"k": BadKeys()}["k"]))
    except TypeError as e:
        print("TypeError", e)
    print(dict(EmptyKeys()))
    try:
        print(dict(RaisesKey()))
    except KeyError as e:
        print("KeyError", e)
    try:
        for k in NoKeys():
            print(k)
    except TypeError as e:
        print("TypeError", e)
    try:
        for k in BadKeys().keys():
            print(k)
    except TypeError as e:
        print("TypeError", e)
main()
'''

PROGRAMS = {
    'mapping_protocol': MAPPING,
    'mapping_failures': FAILURES_CAUGHT,
}


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax",
                            "python", "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class DictMappingProtocol(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            self.assertEqual(want.returncode, 0, want.stderr)
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


if __name__ == '__main__':
    unittest.main()
