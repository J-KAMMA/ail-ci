"""Differential fuzz round 29: class attributes are per class, not per instance.

Found with a small program compared against CPython on both builds:

1. The general path copied every class attribute onto each new instance.  For an immutable
   literal that was invisible, but for a list or dict it gave every instance its own object:
   `a.items.append(1)` left `b.items` empty, where CPython shares the class's list.  A class
   attribute is now evaluated once into a module-lifetime slot and every instance (and `C.K`)
   reads that same object, so mutating it through one instance is visible through all of them;
   assigning `self.items = ...` still shadows it on that one instance, as CPython does.

The other shapes below (inheritance of a shared class attribute, a subclass redefining it,
empty / negative / huge literals, and reads through an argument, a list item and a dict value)
are fuzzed too and compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


SHARED_CLASS_ATTR = r'''class Bag:
    items = []
    counts = {}
    meta = {"hist": []}
    zero = 0
    neg = -5
    big = 1000000

    def __init__(self, name: str) -> None:
        self.name = name

    def add(self, x: int) -> None:
        self.items.append(x)
        self.counts[x] = self.counts.get(x, 0) + 1
        self.meta["hist"].append(x)


def touch(b: Bag, xs: list[int]) -> None:
    for x in xs:
        b.add(x)


def main() -> None:
    a = Bag("a")
    b = Bag("b")
    touch(a, [1, 2, 2])
    touch(b, [3])
    print(a.items, b.items, Bag.items)
    print(a.counts, b.counts, Bag.counts)
    print(a.meta, b.meta, Bag.meta)
    print(a.items is b.items, a.counts is Bag.counts, a.meta is b.meta)
    c = Bag("c")
    print(c.items, c.counts, c.meta)
    print(a.neg, a.big, Bag.neg, Bag.big)
    a.items = ["private"]
    print(a.items, b.items, Bag.items)


main()
'''

INHERITED_CLASS_ATTR = r'''class Base:
    shared: list[int] = []
    tag = "base"
    level = 1

    def add(self, x: int) -> None:
        self.shared.append(x)

    def show(self) -> str:
        return self.tag + ":" + str(self.level) + ":" + str(self.shared)


class Mid(Base):
    tag = "mid"


class Leaf(Mid):
    tag = "leaf"
    level = 3

    def add(self, x: int) -> None:
        super().add(x)
        self.shared.append(-x)


def fill(obj: Base, xs: list[int]) -> None:
    for x in xs:
        obj.add(x)


def main() -> None:
    base = Base()
    mid = Mid()
    leaf = Leaf()
    fill(base, [1])
    fill(mid, [2])
    fill(leaf, [3, 4])
    print(base.show(), mid.show(), leaf.show())
    print(Base.shared, Mid.shared, Leaf.shared)
    print(Base().show(), Mid().show(), Leaf().show())
    print(Base.tag, Mid.tag, Leaf.tag, Base.level, Mid.level, Leaf.level)


main()
'''

CLASS_ATTR_READS = r'''class Config:
    retries = 3
    name = "worker"
    enabled = True
    ratio = 1.5
    empty = ""
    zero = 0


class Holder:
    def __init__(self) -> None:
        self.config = Config()


def values(c: Config) -> tuple[int, str, bool, float]:
    return (c.retries, c.name, c.enabled, c.ratio)


def main() -> None:
    h = Holder()
    print(Config.retries, Config.name, Config.enabled, Config.ratio, repr(Config.empty), Config.zero)
    print(values(Config()), values(h.config))
    print([Config.retries][0], {"r": Config.ratio}["r"], [Config.name for _ in range(2)])
    print(Config.retries + 1, Config.name + "!", not Config.enabled, Config.ratio * 2.0)
    print(f"{Config.retries:03d} {Config.ratio:.2f} {Config.name:>8}")


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


class Fuzz29Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz29-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_shared_mutable_class_attribute(self):
        self.check('shared_class_attr', SHARED_CLASS_ATTR)

    def test_inherited_class_attribute(self):
        self.check('inherited_class_attr', INHERITED_CLASS_ATTR)

    def test_class_attribute_reads(self):
        self.check('class_attr_reads', CLASS_ATTR_READS)


if __name__ == '__main__':
    unittest.main()
