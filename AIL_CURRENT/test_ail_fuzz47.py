"""fuzz47: a mutable default nested inside a tuple is shared between calls, as CPython shares it.

`_hoist_defaults` already evaluated a list/dict/set default once at the `def`, but treated a tuple
as an immutable literal (`ast.literal_eval` accepts `([],)`), so it rebuilt the tuple at every call
and handed out a fresh list inside it. `def f(t=([],))` printed `([1],)` on every call where
CPython prints `([1],)`, `([1, 1],)`, `([1, 1, 1],)`. The tuple is now hoisted too.

Every program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print what
CPython prints with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

TUPLE_LIST = r"""def f(t=([],)):
    t[0].append(1)
    return t

def main():
    print(f())
    print(f())
    print(f())

main()
"""

TUPLE_NESTED = r"""def f(t=(([],),)):
    t[0][0].append(1)
    return t

def main():
    print(f())
    print(f())
    print(f((([9],),)))

main()
"""

TUPLE_DICT_SET = r"""def f(t=({"k": []}, {1})):
    t[0]["k"].append(1)
    t[1].add(2)
    return (len(t[0]["k"]), sorted(t[1]))

def main():
    print(f())
    print(f())
    print(f(t=({"k": [9]}, {1})))

main()
"""

TUPLE_KWONLY = r"""def f(*, t=([],)):
    t[0].append(1)
    return t

def main():
    print(f())
    print(f())
    print(f(t=([9],)))

main()
"""

TUPLE_BYTEARRAY = r"""def f(t=(bytearray(b"a"),)):
    t[0].append(98)
    return bytes(t[0])

def main():
    print(f())
    print(f())
    print(f((bytearray(b"z"),)))

main()
"""

TUPLE_ONCE_AT_DEF = r"""X = 1
def f(t=(X, [])):
    t[1].append(X)
    return t

def main():
    global X
    X = 2
    print(f())
    print(f())

main()
"""

TUPLE_IMMUTABLE = r"""def f(a=(), b=(1, 2), c=(-3, 0), d=(9223372036854775807,)):
    return (a, b, c, d)

def main():
    print(f())
    print(f((1,), (2, 3), (4,), (5,)))
    print(f(b=()))

main()
"""

MUTABLE_DEFAULTS = r"""def f(a=[], d={}, s=set()):
    a.append(len(a))
    d[len(d)] = 1
    s.add(len(s))
    return (len(a), len(d), len(s))

def main():
    print(f())
    print(f())
    print(f(a=[9]))

main()
"""


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz47-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python", "-o", str(exe)],
                               cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


class TupleDefaults(Base):
    def test_list_inside_tuple_is_shared(self):
        out = self.same(TUPLE_LIST)
        self.assertEqual(out, b"([1],)\n([1, 1],)\n([1, 1, 1],)\n")

    def test_nested_tuple_and_explicit_argument(self):
        out = self.same(TUPLE_NESTED)
        self.assertEqual(out, b"(([1],),)\n(([1, 1],),)\n(([9, 1],),)\n")

    def test_dict_and_set_inside_tuple_are_shared(self):
        self.assertTrue(self.same(TUPLE_DICT_SET))

    def test_keyword_only_tuple_default(self):
        out = self.same(TUPLE_KWONLY)
        self.assertEqual(out, b"([1],)\n([1, 1],)\n([9, 1],)\n")

    def test_bytearray_inside_tuple_is_shared(self):
        out = self.same(TUPLE_BYTEARRAY)
        self.assertEqual(out, b"b'ab'\nb'abb'\nb'zb'\n")

    def test_tuple_default_evaluated_once_at_def(self):
        out = self.same(TUPLE_ONCE_AT_DEF)
        self.assertEqual(out, b"(1, [2])\n(1, [2, 2])\n")

    def test_immutable_tuple_defaults(self):
        self.assertTrue(self.same(TUPLE_IMMUTABLE))

    def test_plain_mutable_defaults_still_shared(self):
        out = self.same(MUTABLE_DEFAULTS)
        self.assertEqual(out, b"(1, 1, 1)\n(2, 2, 2)\n(2, 3, 3)\n")


if __name__ == "__main__":
    unittest.main()
