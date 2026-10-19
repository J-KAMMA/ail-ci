"""Three silent differences found by differential fuzzing (lab/fuzz), each compared with CPython.

1. `s[i]` out of range on a str raises a catchable IndexError (it stopped the program).
2. `xs == ys` / `xs != ys` on two `list[int]` compares element by element (it was a C compile error).
3. A def-syntax file that binds a second name to a list/dict/set/bytearray and writes through one name
   while reading the other is refused by name where only the copying emitter could take it (CPython
   shares the object); block-syntax files keep their value semantics.
4. (round 2) alias shapes the fuzzer built (try/else, augmented ops, list == beside a lambda sort key)
   are CPython-identical or refused by name, never a silent difference or a C error; `.lower()` /
   `.upper()` on a non-ASCII str literal is folded at compile time instead of trapping at run time.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STR_INDEX = '''
def main() -> None:
    s: str = "a\\u00f1c"
    for i in [3, -4, 1, -1, 0, 100]:
        try:
            c: str = s[i]
            print(c)
        except IndexError:
            print("caught", i)
    t: str = "abc"
    try:
        print(t[3])
    except IndexError:
        print("caught")
    b: bytes = b"ab"
    try:
        print(b[5])
    except IndexError:
        print("caught bytes")
    print(t[7])


main()
'''

LIST_EQ = '''
def main() -> None:
    a: list[int] = [1, 2]
    b: list[int] = [1, 2]
    c: list[int] = [1]
    e: list[int] = []
    f: list[int] = [1, 3]
    print(a == b, a != b, a == c, a != c, e == [], c == [1], a == f, a != f)
    print(a == [1, 2], [2, 1] == a, e != c)
    if a == b:
        print("same")
    if a != f:
        print("different")
    a.append(5)
    print(a == b, a == [1, 2, 5])


main()
'''

LIST_OTHER = '''
def main() -> None:
    a: list[float] = [0.0, 1.5]
    b: list[float] = [-0.0, 1.5]
    print(a == b, a != b)
    s: list[str] = ["a", "b"]
    t: list[str] = ["a", "b"]
    print(s == t)
    n: list[int] = [1, 2]
    m: list[int] = [1, 3]
    print(n < m, n >= m)


main()
'''

ALIAS = {
    'list': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
             '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_store': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                   '    ys[0] = 9\n    print(xs[0], ys[0])\n\n\nmain()\n'),
    'list_aug': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                 '    xs += [3]\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_loop': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                  '    for i in range(3):\n        print(len(ys))\n        xs.append(i)\n\n\nmain()\n'),
    'dict': ('def main() -> None:\n    d: dict[int, int] = {1: 2}\n    e: dict[int, int] = d\n'
             '    e[5] = 6\n    print(len(d), len(e))\n\n\nmain()\n'),
    'set': ('def main() -> None:\n    s: set[int] = {1, 2}\n    t: set[int] = s\n'
            '    t.add(7)\n    print(len(s), len(t))\n\n\nmain()\n'),
    'bytearray': ('def main() -> None:\n    b: bytearray = bytearray(b"ab")\n    c: bytearray = b\n'
                  '    c.append(99)\n    print(len(b), len(c))\n\n\nmain()\n'),
}

# aliasing that does not differ, or a copy made on purpose: compiles on the copying emitter
ALIAS_FINE = {
    'copy': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs.copy()\n'
             '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_call': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = list(xs)\n'
                  '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'only_alias_read': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                        '    print(len(xs), len(ys))\n\n\nmain()\n'),
    'only_dst_used': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                      '    ys.append(3)\n    print(len(ys))\n\n\nmain()\n'),
    'sorted_copy': ('def main() -> None:\n    xs: list[int] = [3, 1]\n    ys: list[int] = sorted(xs)\n'
                    '    ys.append(0)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
}

# the alias sends these to the general (boxed) path; its `+=`/`|=` change the object in place and its
# str format specs pad by code points
GENERAL = '''
def main() -> None:
    xs: list[int] = [1, 2]
    ys: list[int] = xs
    xs += [3]
    xs += xs
    print(len(xs), len(ys))
    s: set[int] = {1}
    t: set[int] = s
    s |= {2, 3}
    print(len(s), len(t))
    n: int = 5
    n += 2
    z: str = "a"
    z += "b"
    print(n, z)
    u: str = "日本"
    print(f"{u:<6}|{u:^7}|{u:>5}|{u:*^8.1}|{u:.1}|")
    print(f"{'日本':<6}{5:3d}")


main()
'''

# a `return` whose C expression has a multi-line set-up (seed 2074200013): the cleanup rewrite of
# `return e;` cut it in the middle and gcc saw an unterminated function
RETURN_SETUP = '''
def h0(text: str) -> int:
    return text.find("-".join(text.split(",")))


def h1(text: str, other: str) -> int:
    return len(other.join(text.split(","))) + text.find(",".join(other.split("x")))


print(h0("a,b"), h0("a-b,b"), h1("a,b", "zxz"))
'''

# round 2: shapes from the fuzz run (try/else alias with `+=`; list == beside a lambda sort key)
ROUND2 = {
    'try_else_alias': '''
def main() -> int:
    v1: list[int] = [5, 3, 1]
    try:
        print(len(v1))
    except KeyError:
        v6: int = 2
    else:
        al7: list[int] = v1
        al7 += [7]
        print(len(v1), len(al7), sum(v1) - sum(al7))
    finally:
        print(238)
    return 0


main()
''',
    'alias_eq_sortkey': '''
def main() -> int:
    v7: list[int] = [1, 2, 3]
    v9: list[int] = [3, 1, 2]
    v9.sort(key=lambda q: (-q, q))
    al21: list[int] = v7
    al21.append(8)
    print(len(v7), len(al21), sum(v7) - sum(al21))
    print(v7 == al21)
    print(v9)
    return 0


main()
''',
    'aug_ops_alias': '''
def main() -> int:
    xs: list[int] = [1, 2, 3]
    ys: list[int] = xs
    ys *= 2
    s: set[int] = {1, 2, 3}
    t: set[int] = s
    t -= {1}
    t &= {2, 5}
    t ^= {9}
    print(len(xs), len(ys), sorted(s), sorted(t))
    return 0


main()
''',
}

# With AIL_IR=1 the IR takes a def-syntax function whose only sharing is a list (design section 15):
# it shares like CPython, so these compile and print what CPython prints. The other kinds (dict, set,
# bytearray, `+=` on a list) are not in the IR yet: the legacy emitter refuses them by name.
IR_SHARES = ("list", "list_store", "list_loop")
IR_SHARES_TYPED = ("field_read", "field_read_other_way")


def ir_on():
    return os.environ.get("AIL_IR", "1").strip().lower() not in ("0", "off", "no", "false")   # the IR is the default


NONASCII_CASE = '''
def h(a: int) -> str:
    v2: str = "-".join("caf\\u00e9 \\u00d1".lower().split(","))
    return v2 + "stra\\u00dfe".upper()


print(h(1))
print("\\u00c9t\\u00e9".upper(), "\\u00c9t\\u00e9".lower())
'''
BRACE_ALIAS = '''fn main() {
    let xs = [1, 2];
    let ys = xs;
    ys.append(3);
    print(len(xs), len(ys));
}
'''

# C2: every way a container gets a second reference. CPython shares; the typed path copies, so the
# typed path refuses by name (the whole program is then rebuilt on the sharing general path).
BAG = '''class Bag:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

'''
SHARE = {
    'append': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.append(xs)\n'
              '    xs.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'append_via_outer': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.append(xs)\n'
                        '    g[0].append(2)\n    print(len(xs))\n\n\nmain()\n',
    'helper': 'def grow(g: list[list[int]], xs: list[int]) -> None:\n    g.append(xs)\n\n\n'
              'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    grow(g, xs)\n'
              '    xs.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'insert': 'def main() -> None:\n    g: list[list[int]] = [[0]]\n    xs = [1]\n    g.insert(0, xs)\n'
              '    xs.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'extend_display': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.extend([xs])\n'
                      '    xs.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'list_display': 'def main() -> None:\n    xs = [1]\n    g = [xs, [5]]\n    xs.append(2)\n'
                    '    print(len(g[0]))\n\n\nmain()\n',
    'element_store': 'def main() -> None:\n    xs = [1]\n    g: list[list[int]] = [[0]]\n    g[0] = xs\n'
                     '    xs.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'comprehension': 'def main() -> None:\n    xs = [1]\n    g = [xs for _ in range(2)]\n    xs.append(2)\n'
                     '    print(len(g[0]))\n\n\nmain()\n',
    'tuple': 'def main() -> None:\n    xs = [1]\n    t = (xs, 3)\n    xs.append(2)\n    print(len(t[0]))\n\n\nmain()\n',
    'constructor': BAG + 'def main() -> None:\n    ys = [1]\n    b = Bag(ys)\n    ys.append(8)\n'
                   '    print(len(b.xs))\n\n\nmain()\n',
    'constructor_field_write': BAG + 'def main() -> None:\n    ys = [1]\n    b = Bag(ys)\n    b.xs.append(8)\n'
                               '    print(len(ys))\n\n\nmain()\n',
    'field_read': BAG + 'def main() -> None:\n    b = Bag([1])\n    zs = b.xs\n    zs.append(9)\n'
                  '    print(len(b.xs))\n\n\nmain()\n',
    'field_read_other_way': BAG + 'def main() -> None:\n    b = Bag([1])\n    zs = b.xs\n    b.xs.append(9)\n'
                            '    print(len(zs))\n\n\nmain()\n',
    'return_parameter': 'def ident(x: list[int]) -> list[int]:\n    return x\n\n\ndef main() -> None:\n'
                        '    xs = [1]\n    r = ident(xs)\n    r.append(2)\n    print(len(xs))\n\n\nmain()\n',
    'return_field': BAG + 'def get(b: Bag) -> list[int]:\n    return b.xs\n\n\ndef main() -> None:\n'
                    '    b = Bag([1])\n    r = get(b)\n    r.append(2)\n    print(len(b.xs))\n\n\nmain()\n',
    'return_element': 'def first(g: list[list[int]]) -> list[int]:\n    return g[0]\n\n\ndef main() -> None:\n'
                      '    g: list[list[int]] = [[1]]\n    r = first(g)\n    r.append(2)\n    print(len(g[0]))\n\n\nmain()\n',
    'method_store': 'class Bag:\n    def __init__(self) -> None:\n        self.xs: list[int] = []\n\n'
                    '    def put(self, ys: list[int]) -> None:\n        self.xs = ys\n\n\n'
                    'def main() -> None:\n    b = Bag()\n    ys = [1]\n    b.put(ys)\n    ys.append(2)\n'
                    '    print(len(b.xs))\n\n\nmain()\n',
}

# copies, fresh accumulators and read-only uses: the typed path keeps them
SHARE_FINE = {
    'copy_append': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.append(xs.copy())\n'
                   '    xs.append(2)\n    print(len(g[0]), len(xs))\n\n\nmain()\n',
    'slice_append': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.append(xs[:])\n'
                    '    xs.append(2)\n    print(len(g[0]), len(xs))\n\n\nmain()\n',
    'fresh_rows': 'def main() -> None:\n    g: list[list[int]] = []\n    for i in range(3):\n'
                  '        row: list[int] = []\n        for j in range(i + 1):\n            row.append(j)\n'
                  '        g.append(row)\n    print(len(g), len(g[2]))\n\n\nmain()\n',
    'reset_row': 'def main() -> None:\n    g: list[list[int]] = []\n    row: list[int] = []\n'
                 '    for i in range(6):\n        row.append(i)\n        if len(row) == 2:\n'
                 '            g.append(row)\n            row = []\n    print(len(g), len(g[0]))\n\n\nmain()\n',
    'append_no_write': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1, 2]\n    g.append(xs)\n'
                       '    print(len(g[0]), len(xs))\n\n\nmain()\n',
    'rebind_after': 'def main() -> None:\n    g: list[list[int]] = []\n    xs = [1]\n    g.append(xs)\n'
                    '    xs = [9]\n    xs.append(1)\n    print(len(g[0]), len(xs))\n\n\nmain()\n',
    'scalar_append': 'def main() -> None:\n    vals = [3, 1, 2]\n    out: list[int] = []\n'
                     '    for i in range(3):\n        out.append(vals[i])\n    vals.sort()\n'
                     '    print(out[0], vals[0], len(out))\n\n\nmain()\n',
    'ctor_read_only': BAG + 'def main() -> None:\n    ys = [1, 2]\n    b = Bag(ys)\n    print(len(b.xs), len(ys))\n\n\nmain()\n',
    'ctor_copy': BAG + 'def main() -> None:\n    ys = [1]\n    b = Bag(ys.copy())\n    ys.append(8)\n'
                 '    b.xs.append(7)\n    print(len(b.xs), len(ys))\n\n\nmain()\n',
    'field_read_only': BAG + 'def main() -> None:\n    b = Bag([1])\n    zs = b.xs\n    print(len(zs), len(b.xs))\n\n\nmain()\n',
}

# C3: CPython evaluates a default once, so the list/dict is shared between calls (general path)
MUTABLE_DEFAULTS = '''
def add(x: int, acc: list[int] = []) -> int:
    acc.append(x)
    return len(acc)


def tally(k: str, seen: dict[str, int] = {}) -> int:
    seen[k] = seen.get(k, 0) + 1
    return seen[k]


class K:
    def put(self, v: int, buf: list[int] = []) -> int:
        buf.append(v)
        return len(buf)


def main() -> None:
    print(add(1), add(2), add(3))
    print(add(9, [7]), add(4))
    print(tally("a"), tally("a"), tally("b"))
    k = K()
    j = K()
    print(k.put(1), j.put(2), k.put(3))


main()
'''

# C4: a dict or set that changes size while it is walked raises RuntimeError (general path: message too)
CHANGED_SIZE_GENERAL = '''
def main() -> None:
    d: dict[int, int] = {1: 1, 2: 2}
    try:
        for k in d:
            d[k + 10] = 0
    except RuntimeError as e:
        print("caught", e)
    print(len(d))
    e2: dict[int, int] = {1: 1, 2: 2, 3: 3}
    for k in e2:
        e2[k] = e2[k] + 1
    print(sorted(e2.items()))
    try:
        for k in e2:
            del e2[k]
    except RuntimeError as err:
        print("caught", err)
    s: set[int] = {1, 2}
    try:
        for x in s:
            s.add(x + 10)
    except RuntimeError as err:
        print("caught", err)
    print(len(s))
    f: dict[str, int] = {"a": 1}
    try:
        for key, val in f.items():
            f[key + "x"] = val
    except RuntimeError as err:
        print("caught", err)
    try:
        for key in f.keys():
            f["q" + key] = 0
    except RuntimeError as err:
        print("caught", err)
    try:
        for val in f.values():
            f["z"] = 0
    except RuntimeError as err:
        print("caught", err)
    print(len(f))
    g: dict[int, int] = {1: 1, 2: 2}
    for k in g:
        g[k] = 0
    print(g)
    for k in d:
        d[k + 1000] = 1
    print("not reached")


main()
'''
CHANGED_SIZE_TYPED = '''
def main() -> None:
    d: dict[int, int] = {1: 1, 2: 2}
    try:
        for k in d:
            d[k + 10] = 0
    except RuntimeError:
        print("caught")
    print(len(d))
    e2: dict[int, int] = {1: 1, 2: 2, 3: 3}
    for k in e2:
        e2[k] = e2[k] + 1
    print(len(e2))
    try:
        for k in e2:
            del e2[k]
    except RuntimeError:
        print("caught")
    s: set[int] = {1, 2}
    try:
        for x in s:
            s.add(x + 10)
    except RuntimeError:
        print("caught")
    print(len(s))
    f: dict[str, int] = {"a": 1}
    try:
        for key, val in f.items():
            f[key + "x"] = val
    except RuntimeError:
        print("caught")
    try:
        for key in f.keys():
            f["q" + key] = 0
    except RuntimeError:
        print("caught")
    try:
        for val in f.values():
            f["z"] = 0
    except RuntimeError:
        print("caught")
    print(len(f))
    g: dict[int, int] = {1: 1, 2: 2}
    for k in g:
        g[k] = 0
    print(len(g))
    for k in d:
        d[k + 1000] = 1
    print("not reached")


main()
'''

# C12: the refusal names the real reason
MINMAX_STR = 'def main() -> None:\n    print(min("ab", "b"))\n    print(max("ab", "b"))\n\n\nmain()\n'
DICT_ALIAS_UNTYPED = ('def main() -> None:\n    d = {"a": 1}\n    e = d\n    e["b"] = 2\n'
                      '    print(len(d))\n\n\nmain()\n')

# C15: a str element must still be there when a later argument raises
EXCEPT_LIST = '''import sys
from dataclasses import dataclass


@dataclass
class Acc:
    total: int
    names: list[str]


def add(acc: Acc, name: str, v: int) -> None:
    acc.names.append(name)
    acc.total += v


def main() -> int:
    acc = Acc(0, [])
    for line in sys.stdin:
        f = line.split()
        try:
            add(acc, f[0], int(f[1]))
        except ValueError:
            print("bad", f[0])
    print(acc.total, len(acc.names))
    return 0


main()
'''

# C17 (reported, not reproduced): list(d.keys()) / list(d.values()) / list(d.items()) / sorted(d) lengths
DICT_LISTS = '''
def total(ks: list[str]) -> int:
    return len(ks)


def main() -> None:
    names: dict[str, int] = {}
    for w in ["delta", "alpha", "charlie"]:
        names[w] = len(w)
    keys = list(names.keys())
    print(len(keys), keys[1])
    keys.sort()
    print(len(keys), keys[0], total(keys))
    vals = list(names.values())
    vals.append(9)
    print(len(vals), sum(vals))
    ks = list(names)
    sk = sorted(names.keys())
    sv = sorted(names.values())
    print(len(ks), len(sk), sk[0], len(sv))
    pairs = sorted(names.items())
    print(len(pairs), pairs[0][0])
    ik: dict[int, str] = {}
    for i in range(4):
        ik[i * 3] = "v" + str(i)
    il = list(ik.keys())
    print(len(il), il[3], len(list(ik)), len(sorted(ik.keys())))
    iv = list(ik.values())
    print(len(iv), iv[3])
    ii = list(ik.items())
    print(len(ii), ii[3][0], ii[3][1])


main()
'''


def compile_source(directory, text, name, syntax='python', env=None):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', syntax, '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=dict(os.environ, **(env or {})))
    return built, source, exe


def run_both(directory, text, name, env=None):
    """(compile result, AIL run, CPython run) of one def-syntax program."""
    built, source, exe = compile_source(directory, text, name, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected

# (round 3) an int64 overflow is a stop (`AIL limit: int_overflow`, exit 3), not an exception: no `except`
# and no `finally` block may run on the way out. The general path used to run the `finally` bodies first,
# printing lines CPython never prints (fuzz seed 2074400336). `v += [9]` after `a = v` forces that path.
LIMIT_IN_TRY = '''
def main() -> int:
    v: list[int] = [1, 2]
    a: list[int] = v
    v += [9]
    print(len(a))
    try:
        try:
            try:
                x: int = 9223372036854775807 - len(v) * -1
                print(x)
            except:
                print(1)
            finally:
                print(2)
        except ZeroDivisionError:
            print(3)
        else:
            print(70)
        finally:
            print(4)
    finally:
        print(5)
    return 1


main()
'''

LIMIT_IN_HANDLER = '''
def main() -> int:
    v: list[int] = [1, 2]
    a: list[int] = v
    v += [9]
    print(len(a))
    try:
        try:
            print(1 // (len(a) - 3))
        except ZeroDivisionError:
            x: int = 9223372036854775807 - len(v) * -1
            print(x)
        finally:
            print(2)
    finally:
        print(5)
    return 1


main()
'''

# `xs.extend(xs)` on the general path walked xs while appending to it and never ended (out of memory;
# fuzz seed 2074400450). It adds the items xs had when the call began, once.
SELF_EXTEND = '''
def main() -> int:
    v: list[int] = [-3, 0, 3, 6]
    a: list[int] = v
    v.extend(v)
    print(len(v), len(a), sum(a))
    v.extend(a)
    print(len(v), sum(v))
    w: list[int] = list(v)
    w.extend(v)
    print(len(w), sum(w))
    return 1


main()
'''


class FuzzFindings(unittest.TestCase):
    def same_as_cpython(self, text, name, env=None):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, text, name, env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)
            if expected.returncode:
                self.assertIn(b'IndexError: ', expected.stderr)
                self.assertIn(b'string index out of range', ran.stderr)

    def test_str_index_error_is_catchable(self):
        self.same_as_cpython(STR_INDEX, 'stridx')

    def test_str_index_error_is_catchable_ir(self):
        self.same_as_cpython(STR_INDEX, 'stridx_ir', {'AIL_IR': '1'})

    def test_list_int_equality(self):
        self.same_as_cpython(LIST_EQ, 'listeq')
        self.same_as_cpython(LIST_EQ, 'listeq_ir', {'AIL_IR': '1'})

    def test_other_list_comparisons_never_reach_the_c_compiler(self):
        # element kinds the whole-list compare is not built for are answered by another path or
        # refused by name -- never a C compile error (exit 4)
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, LIST_OTHER, 'listother', {'AIL_NO_GENERAL': '1'})
            self.assertIn(built.returncode, (0, 3), built.stdout + built.stderr)
            if built.returncode == 0:
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout))
        self.same_as_cpython(LIST_OTHER, 'listother_general')

    def test_alias_is_refused_by_name_where_only_value_semantics_exist(self):
        for name, text in ALIAS.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = run_both(directory, text, name, {'AIL_NO_GENERAL': '1'})
                    if ir_on() and name in IR_SHARES:
                        # CPython's result: the IR owns the function and shares the list
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout))
                        continue
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    message = built.stdout + built.stderr
                    self.assertIn('makes a second name for the same container', message)
                    self.assertIn('.copy()', message)

    def test_alias_is_cpython_where_a_sharing_path_takes_it(self):
        for name, text in ALIAS.items():
            if name == 'bytearray':
                continue                 # the general path cannot build it: the refusal above stands
            with self.subTest(name):
                self.same_as_cpython(text, name + '_general')
                self.same_as_cpython(text, name + '_general_ir', {'AIL_IR': '1'})

    def test_copies_and_harmless_aliases_still_compile_fast(self):
        for name, text in ALIAS_FINE.items():
            with self.subTest(name):
                self.same_as_cpython(text, name, {'AIL_NO_GENERAL': '1'})

    def test_general_path_in_place_operators_and_unicode_format_specs(self):
        self.same_as_cpython(GENERAL, 'general')
        self.same_as_cpython(GENERAL, 'general_ir', {'AIL_IR': '1'})

    def test_return_with_a_multi_line_setup_is_one_statement(self):
        self.same_as_cpython(RETURN_SETUP, 'retsetup')
        self.same_as_cpython(RETURN_SETUP, 'retsetup_ir', {'AIL_IR': '1'})

    def same_or_named_refusal(self, text, name, env=None):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, text, name, env)
            self.assertIn(built.returncode, (0, 3), built.stdout + built.stderr)
            if built.returncode == 3:
                self.assertIn('not in the subset', built.stdout + built.stderr)
            else:
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_round2_alias_shapes_never_differ_silently(self):
        for name, text in ROUND2.items():
            with self.subTest(name):
                self.same_or_named_refusal(text, name)
                self.same_or_named_refusal(text, name + '_ir', {'AIL_IR': '1'})

    def test_case_mapping_of_non_ascii_literals_is_folded(self):
        self.same_as_cpython(NONASCII_CASE, 'nonascii_case')
        self.same_as_cpython(NONASCII_CASE, 'nonascii_case_ir', {'AIL_IR': '1'})

    def test_check_names_the_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'alias.ail')
            kind = 'dict' if ir_on() else 'list'     # with the IR on, the list alias is shared, not refused
            source.write_text(ALIAS[kind], encoding='utf-8')
            checked = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'check', source.name,
                                      '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                                     timeout=120)
            self.assertIn('makes a second name for the same container', checked.stdout)
            self.assertIn('line 3', checked.stdout)
            if ir_on():
                source.write_text(ALIAS['list'], encoding='utf-8')
                again = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'check', source.name,
                                        '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                                       timeout=120)
                self.assertIn('"status": "passed"', again.stdout)

    def test_block_syntax_keeps_value_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_source(directory, BRACE_ALIAS, 'brace', syntax='ail',
                                                env={'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, b'2 3\n')

    # ---- C2: second references to a container (append / constructor / field read / return ...) ----
    def test_second_references_are_cpython_identical_in_every_mode(self):
        for name, text in SHARE.items():
            with self.subTest(name):
                self.same_as_cpython(text, 'share_' + name)
                self.same_as_cpython(text, 'share_%s_ir' % name, {'AIL_IR': '1'})

    def test_second_references_are_refused_by_name_on_the_typed_path(self):
        for name, text in SHARE.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = run_both(directory, text, 'typed_' + name, {'AIL_NO_GENERAL': '1'})
                    if ir_on() and name in IR_SHARES_TYPED:
                        # the IR owns the function and shares the container: CPython's result
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout))
                        continue
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    self.assertIn('second reference to the same container', built.stdout + built.stderr)

    def test_copies_fresh_accumulators_and_reads_stay_on_the_typed_path(self):
        for name, text in SHARE_FINE.items():
            with self.subTest(name):
                self.same_as_cpython(text, 'fine_' + name, {'AIL_NO_GENERAL': '1'})

    # ---- C3: a mutable default is evaluated once ----
    def test_mutable_defaults_are_shared_between_calls(self):
        self.same_as_cpython(MUTABLE_DEFAULTS, 'mutdefault')
        self.same_as_cpython(MUTABLE_DEFAULTS, 'mutdefault_ir', {'AIL_IR': '1'})

    # ---- C4: changing the size of a dict or set while walking it ----
    def test_changing_size_during_iteration_raises_runtime_error(self):
        for mode, env in (('general', None), ('general_ir', {'AIL_IR': '1'})):
            with self.subTest(mode):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = run_both(directory, CHANGED_SIZE_GENERAL, 'size_' + mode, env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)
                    self.assertEqual(expected.returncode, 1)
                    self.assertIn(b'RuntimeError: dictionary changed size during iteration', ran.stderr)
        for mode, env in (('typed', {'AIL_NO_GENERAL': '1'}),
                          ('typed_ir', {'AIL_NO_GENERAL': '1', 'AIL_IR': '1'})):
            with self.subTest(mode):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = run_both(directory, CHANGED_SIZE_TYPED, 'size_' + mode, env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)
                    self.assertIn(b'RuntimeError: dictionary changed size during iteration', ran.stderr)

    # ---- C12: the refusal names the real reason ----
    def test_refusal_reasons_are_the_real_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = run_both(directory, MINMAX_STR, 'minmax', {'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn('min() over str values is not built', built.stdout + built.stderr)
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = run_both(directory, DICT_ALIAS_UNTYPED, 'dictalias', {'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn('makes a second name for the same container', built.stdout + built.stderr)
        self.same_as_cpython(MINMAX_STR, 'minmax_general')
        self.same_as_cpython(DICT_ALIAS_UNTYPED, 'dictalias_general')

    def test_lists_made_from_dict_views_have_the_right_length(self):
        for name, env in (('dl', {'AIL_NO_GENERAL': '1'}), ('dl_ir', {'AIL_NO_GENERAL': '1', 'AIL_IR': '1'}),
                          ('dl_general', None)):
            self.same_as_cpython(DICT_LISTS, name, env)

    # ---- C15: an argument moved into a call must survive a later argument that raises ----
    def test_str_element_survives_a_later_argument_raising(self):
        data = b'a 1\nb x\nc 3\n'
        for name, env in (('exc', None), ('exc_ir', {'AIL_IR': '1'})):
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, source, exe = compile_source(directory, EXCEPT_LIST, name, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
                    expected = subprocess.run([sys.executable, str(source)], input=data, capture_output=True, timeout=60)
                    self.assertEqual(expected.stdout, b'bad b\n4 2\n')
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    # ---- C16: a limit stop does not run except/finally blocks ----
    def test_int_overflow_stop_runs_no_finally_block(self):
        for text, label in ((LIMIT_IN_TRY, 'try'), (LIMIT_IN_HANDLER, 'handler')):
            for mode, env in (('default', None), ('ir', {'AIL_IR': '1'})):
                with self.subTest(label + '_' + mode):
                    with tempfile.TemporaryDirectory() as directory:
                        built, ran, _ = run_both(directory, text, 'limit_' + label + '_' + mode, env)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        self.assertEqual(ran.returncode, 3, ran.stderr)
                        self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), b'3\n')   # Windows text-mode stdout writes CRLF
                        self.assertIn(b'AIL limit: int_overflow', ran.stderr)

    def test_list_extend_with_itself_adds_the_items_once(self):
        for name, env in (('selfext', None), ('selfext_ir', {'AIL_IR': '1'})):
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = run_both(directory, SELF_EXTEND, name, env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual(expected.stdout.replace(b'\r\n', b'\n'), b'8 8 12\n16 24\n32 48\n')
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)


if __name__ == '__main__':
    unittest.main()
