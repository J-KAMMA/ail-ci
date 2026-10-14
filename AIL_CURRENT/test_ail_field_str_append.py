"""`obj.f += s` on a str field grows the field's buffer in place (pyfunc `_attr_augassign`,
`ail_obj_field_str_append`) and prints exactly what Python prints, including self-appends,
appends of a slice of the field itself, shared objects and non-ASCII text. A 300,000-step
append loop must stay small: the general path kept every intermediate string alive.
"""
import subprocess
import sys
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

sys.path[:0] = [str(support.ROOT / 'python' / 'pkg-v12'), str(support.ROOT)]
import pyfunc  # noqa: E402
from ail_syntax import translate  # noqa: E402

SOURCE = r'''struct B { s: str; n: int; }
fn tag(b: B) -> str { return "<" + b.s + ">"; }
fn main() -> int {
    let b = B("", 0);
    for w in "ab é 日本 x".split(" ") { b.s += w; b.s += ","; }
    print(b.s, len(b.s));
    b.s += b.s;
    print(b.s, len(b.s));
    b.s += b.s[2:5];
    print(b.s);
    let c = b;
    c.s += "!";
    print(b.s == c.s, len(b.s));
    let t = b.s;
    b.s += "?";
    print(t, b.s);
    b.s = b.s + "=";
    b.s += tag(b);
    print(b.s);
    let r = B("abcdefghij", 0);
    r.s = "";
    r.s += "x";
    r.s += "yz";
    print(r.s, len(r.s));
    r.s = "longer than sixteen bytes here";
    r.s = r.s[7:13];
    print(r.s);
    r.s = r.s + r.s;
    r.s = "é日";
    r.s += "a";
    print(r.s, len(r.s));
    for i in range(50) { r.s = ""; r.s += str(i); r.s += "-"; }
    print(r.s);
    let big = B("", 0);
    for i in range(300000) { big.s += "x"; }
    print(len(big.s), big.s[299995:]);
    return 0;
}
'''

PYTHON = r'''
class B:
    def __init__(self, s, n): self.s = s; self.n = n
def tag(b): return "<" + b.s + ">"
b = B("", 0)
for w in "ab é 日本 x".split(" "): b.s += w; b.s += ","
print(b.s, len(b.s))
b.s += b.s; print(b.s, len(b.s))
b.s += b.s[2:5]; print(b.s)
c = b; c.s += "!"; print(b.s == c.s, len(b.s))
t = b.s; b.s += "?"; print(t, b.s)
b.s = b.s + "="; b.s += tag(b); print(b.s)
r = B("abcdefghij", 0)
r.s = ""; r.s += "x"; r.s += "yz"; print(r.s, len(r.s))
r.s = "longer than sixteen bytes here"; r.s = r.s[7:13]; print(r.s)
r.s = r.s + r.s; r.s = "é日"; r.s += "a"; print(r.s, len(r.s))
for i in range(50):
    r.s = ""; r.s += str(i); r.s += "-"
print(r.s)
big = B("", 0)
for i in range(300000): big.s += "x"
print(len(big.s), big.s[299995:])
'''


class FieldStrAppendTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_matches_python_and_stays_small(self):
        c = pyfunc.to_c(translate(SOURCE), name='run', strict=True)
        # Every `+=` with a call-free right side is in place; `b.s += tag(b)` is not.
        self.assertEqual(c.count('ail_obj_field_str_append(&'), 13)
        program = build(self, 'field_append', SOURCE)
        result = subprocess.run(['/usr/bin/time', '-f', '%M', str(program)], capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        want = subprocess.run([sys.executable, '-c', PYTHON], capture_output=True, check=True).stdout
        self.assertEqual(result.stdout, want)
        self.assertLess(int(result.stderr.decode().split()[-1]), 20000)   # KiB


if __name__ == '__main__':
    unittest.main()
