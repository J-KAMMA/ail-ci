"""Differential round 78: `**` in a dict literal only takes a mapping.

`{**xs}` with a list (or a str, set, tuple, int) is CPython's
`TypeError: 'list' object is not a mapping`.  The surface rewrite merged the
parts with `_ail_dmerge`, which did `for k in d: out[k] = d[k]`: a non-mapping
iterable was read as a list of keys and then indexed by those keys.  For
`[1, 2]` it set `out[1] = 2` and then indexed out of range (IndexError), and
for an empty list or an empty str it silently produced `{}`.  The helper now
raises TypeError when the part has no `keys()`, so the construct is
CPython-identical (catchable, and an uncaught one exits 1 as CPython does).
A part that is not a dict but does have `keys()` is a mapping: ChainMap and
custom classes with `keys` / `__getitem__` are merged through `keys()`, as
CPython does (`__iter__` is not consulted).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DICT_STAR_NON_MAPPING = r'''class Box:
    pass


def show(d) -> None:
    try:
        print({**d})
    except TypeError:
        print("TypeError")


def main() -> None:
    xs: list[int] = [1, 2]
    empty: list[int] = []
    s: str = "ab"
    st: set[int] = {5, 6}
    box: Box = Box()
    box.d = xs
    dd: dict[str, list[int]] = {"v": xs}
    show(xs)
    show(empty)
    show("")
    show(s)
    show(st)
    show(5)
    show(box.d)
    show(dd["v"])
    show(())
    print("done")


main()
'''

DICT_STAR_OK = r'''from collections import ChainMap, defaultdict


def main() -> None:
    a: dict[str, int] = {"x": 1, "y": 2}
    b: dict[str, int] = {"y": 20, "z": 3}
    print({**a, **b})
    print({**a, "y": 99})
    print({**{}})
    print({**a, **a})
    print(len({**a, **b}))
    alias: dict[str, int] = a
    print({**alias})
    d: defaultdict[str, int] = defaultdict(int)
    d["a"] = 1
    d["b"] = 2
    print({**d})
    print({**{"q": 0}, **a, "z": 9})
    cm: ChainMap[str, int] = ChainMap(a, b)
    print({**cm})
    print({**cm, "w": 4})
    print("done")


main()
'''

DICT_STAR_PROTOCOL = r'''class Map:
    def __init__(self) -> None:
        self.data: dict[str, int] = {"a": 1, "b": 2}

    def keys(self) -> list[str]:
        return ["a", "b"]

    def __iter__(self):
        return iter(["a", "b"])

    def __getitem__(self, k: str) -> int:
        return self.data[k]


class KeysOnly:
    def __init__(self) -> None:
        self.data: dict[str, int] = {"k": 7}

    def keys(self) -> list[str]:
        return ["k"]

    def __getitem__(self, k: str) -> int:
        return self.data[k]


class Weird:
    def __init__(self) -> None:
        self.data: dict[str, int] = {"a": 1, "b": 2}

    def keys(self) -> list[str]:
        return ["a"]

    def __iter__(self):
        return iter(["b"])

    def __getitem__(self, k: str) -> int:
        return self.data[k]


class Box:
    pass


def show(d) -> None:
    print({**d})


def main() -> None:
    m: Map = Map()
    k: KeysOnly = KeysOnly()
    w: Weird = Weird()
    show(m)
    show(k)
    show(w)
    print({**m, "c": 3})
    print({**k, **m, "a": 9})
    rows: list[Map] = [m]
    show(rows[0])
    box: Box = Box()
    box.m = m
    show(box.m)
    dd: dict[str, Map] = {"m": m}
    show(dd["m"])
    print("done")


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


class Fuzz78Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz78-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_dict_star_non_mapping(self):
        self.check('dict_star_non_mapping', DICT_STAR_NON_MAPPING)

    def test_dict_star_mapping(self):
        self.check('dict_star_mapping', DICT_STAR_OK)

    def test_dict_star_mapping_protocol(self):
        self.check('dict_star_mapping_protocol', DICT_STAR_PROTOCOL)


if __name__ == '__main__':
    unittest.main()
