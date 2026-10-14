"""A top-level user definition named like a built-in is what every reference to that name calls.

`fn abs(x: int) -> int { return x * 4; }` then `print(abs(2))` printed 2 (the built-in abs) where
CPython prints 8: the compiler dispatches built-ins by name in many places (pyfunc call lowering,
heapq/bisect, sort keys, nested lists, bool scans, the general path) and none of them asked whether
the program had its own definition. pkg-v12/shadowing.py renames each shadowing module-level
definition (and every reference Python's scoping resolves to it) before any pass runs. Checked
here against CPython running the same programs: ~35 shadowed Python and AIL built-ins called in
expressions, as sort keys, in comprehensions, through Callable values and lambdas; parameters,
locals, comprehension variables, struct methods and fields keeping their own meaning; `print` and
`range` themselves; and the names that cannot be redefined being refused with file:line and a
rename suggestion instead of silently calling the built-in.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MANY = """const id = 7;
struct map { k: int; v: int; }
impl map {
    fn len(self) -> int { return self.k + self.v; }
    fn abs(self) -> int { return self.k * 100; }
}
fn abs(x: int) -> int { return x * 4; }
fn min(a: int, b: int) -> int { return a * 10 + b; }
fn max(a: int, b: int) -> int { return a - b; }
fn sum(xs: list[int]) -> int { return len(xs) * 1000; }
fn len(xs: list[int]) -> int { return 3; }
fn sorted(x: int) -> int { return x + 11; }
fn reversed(x: int) -> int { return 0 - x; }
fn ord(s: str) -> int { return 42; }
fn chr(x: int) -> str { return "c" + str(x); }
fn any(x: int) -> int { return x % 7; }
fn all(x: int) -> int { return x % 5; }
fn round(x: int) -> int { return x * x; }
fn divmod(a: int, b: int) -> int { return a * b; }
fn pow(a: int, b: int) -> int { return a + b; }
fn hex(x: int) -> int { return x + 16; }
fn bin(x: int) -> int { return x + 2; }
fn oct(x: int) -> int { return x + 8; }
fn input(x: int) -> int { return x * 3; }
fn hash(x: int) -> int { return x % 13; }
fn heappush(a: int, b: int) -> int { return a * 100 + b; }
fn heappop(x: int) -> int { return x - 1; }
fn heapify(x: int) -> int { return x * 2; }
fn bisect_left(x: int) -> int { return x + 1000; }
fn bisect(x: int) -> int { return x + 2000; }
fn insort(x: int) -> int { return x + 3000; }
fn read_stdin_bytes(x: int) -> int { return x + 4000; }
fn read_bytes(s: str) -> str { return s + "!"; }
fn wrapping_add(a: int, b: int) -> int { return a * b * 2; }
fn wrapping_mul(a: int, b: int) -> int { return a - b - 1; }
fn monotonic_ms() -> int { return 123; }
fn apply(f: Callable[[int], int], x: int) -> int { return f(x); }
fn uses_param(max: int, xs: list[int]) -> int {
    let total = 0;
    for v in xs { total += v; }
    return max + total;
}
fn shadow_local() -> int { let abs = 3; return abs + 1; }
fn main() {
    let xs: list[int] = [5, -3, 8, -1, 2];
    print(abs(2), min(3, 4), max(9, 2), sum(xs), len(xs));
    print(sorted(1), reversed(4), ord("a"), chr(9), any(20), all(13));
    print(round(6), divmod(6, 7), pow(2, 10), hex(1), bin(1), oct(1), input(5), hash(40));
    print(heappush(3, 4), heappop(10), heapify(21), bisect_left(1), bisect(2), insort(3));
    print(read_stdin_bytes(5), read_bytes("ab"), wrapping_add(3, 4), wrapping_mul(10, 3), monotonic_ms());
    print(abs(min(1, 2)) + max(abs(3), hex(4)) * pow(round(2), 1));
    let ys: list[int] = [3, -7, 1, 6, -2];
    ys.sort(key=abs);
    print(ys[0], ys[1], ys[2], ys[3], ys[4]);
    let zs: list[int] = [4, 9, 2, 7];
    zs.sort(key=reversed);
    print(zs[0], zs[1], zs[2], zs[3]);
    let ws = [abs(v) + hash(v) for v in xs if any(v) != 0];
    print(ws[0], ws[1], ws[2], len(ws));
    let qs = [min(v, v) for v in range(3)];
    print(qs[0], qs[1], qs[2]);
    let cs = [abs + 1 for abs in [10, 20]];
    print(cs[0], cs[1], shadow_local());
    let f: Callable[[int], int] = bin;
    let g: Callable[[int], int] = heappop;
    print(f(5), g(5), apply(input, 6), apply(oct, 6), apply(sorted, 1));
    print(uses_param(100, xs), id, id + abs(id));
    let m = map(2, 3);
    print(m.len(), m.abs(), abs(m.k));
}
"""

MANY_PY = """id = 7
class map:
    def __init__(self, k, v): self.k, self.v = k, v
    def len(self): return self.k + self.v
    def abs(self): return self.k * 100
def abs(x): return x * 4
def min(a, b): return a * 10 + b
def max(a, b): return a - b
def sum(xs): return len(xs) * 1000
def len(xs): return 3
def sorted(x): return x + 11
def reversed(x): return 0 - x
def ord(s): return 42
def chr(x): return "c" + str(x)
def any(x): return x % 7
def all(x): return x % 5
def round(x): return x * x
def divmod(a, b): return a * b
def pow(a, b): return a + b
def hex(x): return x + 16
def bin(x): return x + 2
def oct(x): return x + 8
def input(x): return x * 3
def hash(x): return x % 13
def heappush(a, b): return a * 100 + b
def heappop(x): return x - 1
def heapify(x): return x * 2
def bisect_left(x): return x + 1000
def bisect(x): return x + 2000
def insort(x): return x + 3000
def read_stdin_bytes(x): return x + 4000
def read_bytes(s): return s + "!"
def wrapping_add(a, b): return a * b * 2
def wrapping_mul(a, b): return a - b - 1
def monotonic_ms(): return 123
def apply(f, x): return f(x)
def uses_param(max, xs):
    total = 0
    for v in xs: total += v
    return max + total
def shadow_local():
    abs = 3
    return abs + 1
def main():
    xs = [5, -3, 8, -1, 2]
    print(abs(2), min(3, 4), max(9, 2), sum(xs), len(xs))
    print(sorted(1), reversed(4), ord("a"), chr(9), any(20), all(13))
    print(round(6), divmod(6, 7), pow(2, 10), hex(1), bin(1), oct(1), input(5), hash(40))
    print(heappush(3, 4), heappop(10), heapify(21), bisect_left(1), bisect(2), insort(3))
    print(read_stdin_bytes(5), read_bytes("ab"), wrapping_add(3, 4), wrapping_mul(10, 3), monotonic_ms())
    print(abs(min(1, 2)) + max(abs(3), hex(4)) * pow(round(2), 1))
    ys = [3, -7, 1, 6, -2]
    ys.sort(key=abs)
    print(ys[0], ys[1], ys[2], ys[3], ys[4])
    zs = [4, 9, 2, 7]
    zs.sort(key=reversed)
    print(zs[0], zs[1], zs[2], zs[3])
    ws = [abs(v) + hash(v) for v in xs if any(v) != 0]
    print(ws[0], ws[1], ws[2], len(ws))
    qs = [min(v, v) for v in range(3)]
    print(qs[0], qs[1], qs[2])
    cs = [abs + 1 for abs in [10, 20]]
    print(cs[0], cs[1], shadow_local())
    f = bin
    g = heappop
    print(f(5), g(5), apply(input, 6), apply(oct, 6), apply(sorted, 1))
    print(uses_param(100, xs), id, id + abs(id))
    m = map(2, 3)
    print(m.len(), m.abs(), abs(m.k))
main()
"""

STRUCTURAL = """fn print(a: int, b: int) -> void {
    write_stdout_bytes((str(a * b) + "\\n").encode());
}
fn range(n: int) -> list[int] { return [n, n * 2, n * 3]; }
fn zip(a: int) -> int { return a + 5; }
fn enumerate(a: int) -> int { return a * 7; }
fn main() {
    let t = 0;
    for i in range(4) { t += i; }
    print(t, 2);
    let xs: list[int] = [3, -1, 2];
    xs.sort(key=lambda v: zip(v) * -1);
    print(xs[0], 100);
    print(xs[2], 1);
    let ys = [enumerate(v) for v in range(1)];
    print(ys[0] + ys[1] + ys[2], 1);
}
"""

STRUCTURAL_PY = """import sys
def print(a, b): sys.stdout.write(str(a * b) + "\\n")
def range(n): return [n, n * 2, n * 3]
def zip(a): return a + 5
def enumerate(a): return a * 7
def main():
    t = 0
    for i in range(4): t += i
    print(t, 2)
    xs = [3, -1, 2]
    xs.sort(key=lambda v: zip(v) * -1)
    print(xs[0], 100)
    print(xs[2], 1)
    ys = [enumerate(v) for v in range(1)]
    print(ys[0] + ys[1] + ys[2], 1)
main()
"""

# (source, name the refusal must quote, AIL line it must point at)
REFUSED = [
    ('fn int(x: str) -> int { return 5; }\nfn main() { print(int("3")); }', 'int', 1),
    ('fn main() { print(str(1)); }\nfn str(x: int) -> int { return 5; }', 'str', 2),
    ('fn list(n: int) -> int { return n; }\nfn main() { print(list(2)); }', 'list', 1),
    ('fn dict(n: int) -> int { return n; }\nfn main() { print(dict(2)); }', 'dict', 1),
    ('fn bool(n: int) -> int { return n; }\nfn main() { print(bool(2)); }', 'bool', 1),
    ('const float = 3;\nfn main() { print(float); }', 'float', 1),
    ('fn bytearray(n: int) -> int { return n; }\nfn main() { print(bytearray(2)); }', 'bytearray', 1),
    ('fn par_range(a: int, b: int) -> int { return a; }\nfn main() { print(par_range(1, 2)); }', 'par_range', 1),
    ('struct ValueError { a: int; }\nfn main() { let e = ValueError(3); print(e.a); }', 'ValueError', 2),
]


def build(directory, name, text):
    source = Path(directory, name + '.ail')
    source.write_text(text, encoding='utf8')
    output = Path(directory, name)
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                             '-o', str(output)], capture_output=True, text=True, timeout=300)
    return result, output


def cpython(directory, text):
    oracle = Path(directory, 'oracle.py')
    oracle.write_text(text, encoding='utf8')
    return subprocess.run([sys.executable, '-I', str(oracle)], capture_output=True, text=True,
                          timeout=60, check=True).stdout


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'), 'installed C compiler required')
class BuiltinShadowingTests(unittest.TestCase):
    def check_against_cpython(self, ail, python):
        with tempfile.TemporaryDirectory() as directory:
            result, output = build(directory, 'p', ail)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            run = subprocess.run([str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual((run.returncode, run.stderr), (0, ''))
            self.assertEqual(run.stdout, cpython(directory, python))

    def test_shadowed_builtins_are_called_everywhere_like_cpython(self):
        self.check_against_cpython(MANY, MANY_PY)

    def test_print_range_and_lambda_keys_like_cpython(self):
        self.check_against_cpython(STRUCTURAL, STRUCTURAL_PY)

    def test_names_that_cannot_be_redefined_are_refused_by_line(self):
        with tempfile.TemporaryDirectory() as directory:
            for text, name, line in REFUSED:
                with self.subTest(name=name):
                    result, output = build(directory, 'r_' + name, text)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())
                    message = result.stderr + result.stdout
                    self.assertIn("r_%s.ail:%d:" % (name, line), message)
                    self.assertIn("'%s' shadows the built-in" % name, message)
                    self.assertIn("rename it (e.g. 'my_%s')" % name, message)


class RenameUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            import shadowing
            from pyfront import Unsupported
        finally:
            sys.path.pop(0)
        cls.shadowing, cls.Unsupported = shadowing, Unsupported

    def test_every_declared_plain_builtin_is_shadowable_or_refused(self):
        from ail_builtin_api import DECLARATIONS
        from ail_builtin_syntax_forms import SYNTAX_FORMS
        s = self.shadowing
        handled = s.SHADOWABLE | s._CORE_TYPES | s._EXCEPTIONS | set(s._STRUCTURAL)
        plain = {name for name in [*DECLARATIONS, *SYNTAX_FORMS] if name.isidentifier()}
        self.assertEqual(sorted(plain - handled - {'file_chunks'}), [])

    def test_type_named_function_is_refused_only_when_read(self):
        unused = 'def bool(value: int) -> int:\n    return value * 2\n\ndef main(flag: bool) -> int:\n    return 0\n'
        self.assertEqual(self.shadowing.rename(unused, self.Unsupported), (unused, {}))
        called = unused.replace('return 0', 'return bool(3)')
        with self.assertRaises(self.Unsupported) as caught:
            self.shadowing.rename(called, self.Unsupported)
        self.assertEqual(caught.exception.source_line, 1)
        self.assertIn("'bool' shadows the built-in type bool", str(caught.exception))

    def test_untouched_program_is_returned_as_is(self):
        source = 'def helper(x):\n    return abs(x) + max(x, 1)\n\ndef main():\n    print(helper(-2))\n'
        renamed, mapping = self.shadowing.rename(source, self.Unsupported)
        self.assertIs(renamed, source)
        self.assertEqual(mapping, {})

    def test_only_global_references_are_renamed_and_lines_stay(self):
        source = ('\n\ndef abs(x):\n    return x * 4\n\nclass P:\n    abs: int\n    def abs2(self):\n'
                  '        return abs(self.abs)\n\ndef f(abs, ys):\n    return abs + [abs for abs in ys][0]\n\n'
                  'def g(ys):\n    ys.sort(key=abs)\n    h = lambda abs: abs\n    return [abs(y) for y in ys], h(abs)\n')
        renamed, mapping = self.shadowing.rename(source, self.Unsupported)
        self.assertEqual(mapping, {'py_abs': 'abs'})
        self.assertEqual(renamed.count('\n'), source.count('\n'))
        expected = source.replace('def abs(', 'def py_abs(').replace(
            'return abs(self.abs)', 'return py_abs(self.abs)').replace(
            'key=abs)', 'key=py_abs)').replace('[abs(y)', '[py_abs(y)').replace('h(abs)', 'h(py_abs)')
        self.assertEqual(renamed, expected)

    def test_fresh_name_avoids_user_names(self):
        source = 'def abs(x):\n    return x\n\ndef py_abs(x):\n    return abs(x)\n'
        renamed, mapping = self.shadowing.rename(source, self.Unsupported)
        self.assertEqual(mapping, {'py_abs_2': 'abs'})
        self.assertIn('def py_abs(x):\n    return py_abs_2(x)', renamed)


if __name__ == '__main__':
    unittest.main()
