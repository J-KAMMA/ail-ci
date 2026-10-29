"""ipaddress.IPv4Address on the general path (stdtop.py + prelude_ipaddress.py), compared with CPython 3.12.

* the prelude runs under CPython next to ipaddress.IPv4Address: generated strings (valid and broken in every way the
  parser distinguishes), ints, bytes and other objects must give the same address, the same exception class and the
  same text; so must the operators, the properties, hash/equality in sets and dicts, and the format types;
* a Python program is compiled with the default build and with AIL_UNIFIED_FORCE=1 and must print the same bytes as
  CPython on generated stdin;
* what is not built (IPv6, networks, ip_address(), is_private / is_global) is refused at compile time by name with
  `write instead:`.
"""
import ipaddress
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
for each in (str(PKG), str(ROOT)):
    if each not in sys.path:
        sys.path.insert(0, each)

PROGRAM = r'''
import ipaddress
import sys


def show(label, f):
    try:
        v = f()
        print(label, "->", v if isinstance(v, (int, bool, str, bytes)) else repr(v))
    except Exception as e:
        print(label, "!!", type(e).__name__, e)


def key(text: str) -> ipaddress.IPv4Address:
    return ipaddress.IPv4Address(text)


def main():
    good = []
    for line in sys.stdin.read().split("\n"):
        show("new " + repr(line), lambda: ipaddress.IPv4Address(line))
        show("  int", lambda: int(ipaddress.IPv4Address(line)))
        show("  props", lambda: (ipaddress.IPv4Address(line).is_loopback, ipaddress.IPv4Address(line).is_multicast,
                                  ipaddress.IPv4Address(line).is_link_local, ipaddress.IPv4Address(line).is_unspecified,
                                  ipaddress.IPv4Address(line).is_reserved))
        show("  rev", lambda: ipaddress.IPv4Address(line).reverse_pointer)
        show("  packed", lambda: ipaddress.IPv4Address(line).packed)
        show("  add", lambda: ipaddress.IPv4Address(line) + 1)
        show("  sub", lambda: ipaddress.IPv4Address(line) - 5)
        try:
            good.append(ipaddress.IPv4Address(line))
        except ipaddress.AddressValueError:
            pass
    print(sorted(good))
    print(len(set(good)), max(good) if good else None, min(good) if good else None)
    print(sorted(set(good)) == sorted(good), {a: str(a) for a in good[:3]})
    show("int", lambda: ipaddress.IPv4Address(3221225985))
    show("neg", lambda: ipaddress.IPv4Address(-1))
    show("big", lambda: ipaddress.IPv4Address(2 ** 32))
    show("bytes", lambda: ipaddress.IPv4Address(b"\x01\x02\x03\x04"))
    show("bytes2", lambda: ipaddress.IPv4Address(b"\x01\x02\x03"))
    show("none", lambda: ipaddress.IPv4Address(None))
    show("float", lambda: ipaddress.IPv4Address(1.5))
    show("bool", lambda: ipaddress.IPv4Address(True))
    a = ipaddress.IPv4Address("10.0.0.1")
    b = ipaddress.IPv4Address("10.0.0.10")
    show("cmp", lambda: (a < b, a <= b, a > b, a >= b, a == b, a != b, a == ipaddress.IPv4Address("10.0.0.1"), a == "10.0.0.1"))
    show("cmp str", lambda: a < "x")
    show("sorted", lambda: sorted([b, a, ipaddress.IPv4Address("9.255.255.255")]))
    show("set", lambda: len({a, b, ipaddress.IPv4Address("10.0.0.1")}))
    show("dict", lambda: {a: 1}[ipaddress.IPv4Address("10.0.0.1")])
    show("fmt", lambda: f"{a} {a!s} {a!r} {a:>12s}|")
    for sp in ["b", "n", "x", "X", "#b", "_b", "#_x", "#_X", "s", ">12s", "q", "10", "bb", "_#b", ""]:
        show("fmt " + sp, lambda: format(a, sp))
    show("add str", lambda: a + "x")
    show("add big", lambda: ipaddress.IPv4Address("255.255.255.255") + 1)
    show("max", lambda: max(a, b))
    show("v", lambda: (a.version, a.max_prefixlen, a.compressed, a.exploded))
    print(sorted(["10.0.0.10", "9.0.0.1", "10.0.0.2"], key=key))
    try:
        ipaddress.IPv4Address("1.2.3")
    except ipaddress.AddressValueError as e:
        print("AVE", e)
    try:
        ipaddress.IPv4Address("1.2.3.x")
    except ValueError as e:
        print("VE", e)


main()
'''

LINES = "\n".join([
    "192.168.1.1", "0.0.0.0", "255.255.255.255", "127.0.0.1", "224.0.0.1", "239.255.255.255", "169.254.1.1", "240.0.0.1",
    "10.0.0.255", "1.2.3", "1.2.3.4.5", "256.1.1.1", "1.2.3.-1", "01.2.3.4", "1.2.3.04", "1.2.3.4/24", "1.2.3.1000", "1.2.3.",
    ".1.2.3", "", " 1.2.3.4", "1.2.3.4 ", "٣.2.3.4", "a.b.c.d", "1.2.3.4a", "00.0.0.0", "1.2.3.0", "999.1.1.1",
    "10.0.0.1", "10.0.0.1"]) + "\n"


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, **env))
    return built, source, exe


def attempt(f):
    try:
        v = f()
        return ("ok", v)
    except Exception as e:
        return ("err", type(e).__name__, str(e))


class PreludeIPv4(unittest.TestCase):
    def test_matches_ipaddress(self):
        import prelude_ipaddress as P
        rnd = random.Random(33)
        pieces = ["0", "1", "9", "10", "99", "100", "127", "192", "199", "200", "249", "255", "256", "300", "999", "1000", "00", "01",
                  "007", "000", "-1", "+1", "1_0", "0x1", "a", "", " ", "٣", "²", "1e1", "1.0"]
        strings = []
        for _ in range(2500):
            strings.append(".".join(rnd.choice(pieces) for _ in range(rnd.choice([4, 4, 4, 3, 5, 1, 2]))))
        strings += ["", "/", "1.2.3.4/32", "1.2.3.4/", " 1.2.3.4", "1.2.3.4\n", "1..2.3", "....", "1.2.3.4.", "::1", "1.2.3.4%eth0"]
        for text in strings:
            want = attempt(lambda: (str(ipaddress.IPv4Address(text)), int(ipaddress.IPv4Address(text))))
            got = attempt(lambda: (str(P.IPv4Address(text)), int(P.IPv4Address(text))))
            self.assertEqual(got, want, repr(text))
        for value in [0, 1, 255, 256, 2 ** 31, 2 ** 32 - 1, 2 ** 32, 2 ** 70, -1, -2 ** 40, True, False, None, 1.5, [1], (1, 2),
                      b"", b"\x01\x02\x03", b"\x01\x02\x03\x04", b"\xff\xff\xff\xff", b"\x00" * 5, bytearray(b"abcd"), "1.2.3.4"]:
            want = attempt(lambda: str(ipaddress.IPv4Address(value)))
            got = attempt(lambda: str(P.IPv4Address(value)))
            self.assertEqual(got, want, repr(value))

    def test_operators_and_properties(self):
        import prelude_ipaddress as P
        rnd = random.Random(8)
        values = [0, 1, 255, 256, 2 ** 24, 2 ** 31, 2 ** 32 - 1] + [rnd.randrange(2 ** 32) for _ in range(300)]
        for v in values:
            c, m = ipaddress.IPv4Address(v), P.IPv4Address(v)
            self.assertEqual((str(m), repr(m), int(m), m.packed, m.version, m.max_prefixlen, m.compressed, m.exploded,
                              m.reverse_pointer, m.is_multicast, m.is_unspecified, m.is_loopback, m.is_link_local, m.is_reserved),
                             (str(c), repr(c), int(c), c.packed, c.version, c.max_prefixlen, c.compressed, c.exploded,
                              c.reverse_pointer, c.is_multicast, c.is_unspecified, c.is_loopback, c.is_link_local, c.is_reserved))
            for other in (0, 1, -1, 7, 2 ** 32 - 1 - v, 2 ** 32 - v, "x", None, 1.5):
                self.assertEqual(attempt(lambda: str(m + other)), attempt(lambda: str(c + other)), (v, other))
                self.assertEqual(attempt(lambda: str(m - other)), attempt(lambda: str(c - other)), (v, other))
            for w in rnd.sample(values, 4) + ["1.2.3.4", None, 5]:
                oc = ipaddress.IPv4Address(w) if isinstance(w, int) and not isinstance(w, bool) and 0 <= w < 2 ** 32 else w
                om = P.IPv4Address(w) if isinstance(w, int) and not isinstance(w, bool) and 0 <= w < 2 ** 32 else w
                for name, fn in [("==", lambda x, y: x == y), ("!=", lambda x, y: x != y), ("<", lambda x, y: x < y),
                                 ("<=", lambda x, y: x <= y), (">", lambda x, y: x > y), (">=", lambda x, y: x >= y)]:
                    self.assertEqual(attempt(lambda: fn(m, om)), attempt(lambda: fn(c, oc)), (name, v, w))
            for spec in ["", "s", ">20s", "b", "n", "x", "X", "#b", "_b", "#_x", "#_X", "q", "10", "bb", "_#b", "#", "_", "xs"]:
                self.assertEqual(attempt(lambda: format(m, spec)), attempt(lambda: format(c, spec)), (v, spec))
        self.assertEqual(len({P.IPv4Address("1.2.3.4"), P.IPv4Address(16909060), P.IPv4Address(b"\x01\x02\x03\x04")}), 1)
        self.assertEqual({P.IPv4Address(5): "a"}[P.IPv4Address("0.0.0.5")], "a")


class CompiledProgram(unittest.TestCase):
    def test_matches_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, PROGRAM, "ip", **env)
                self.assertEqual(built.returncode, 0, "%r\n%s%s" % (env, built.stdout, built.stderr))
                want = subprocess.run([sys.executable, "-X", "utf8", str(source)], input=LINES.encode(), capture_output=True)
                got = subprocess.run([str(exe)], input=LINES.encode(), capture_output=True)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    self.assertEqual(x, y, "line %d %r" % (n + 1, env))
                self.assertEqual(len(a), len(b))


class Refusals(unittest.TestCase):
    CASES = {
        "ip_address": ("import ipaddress\nprint(ipaddress.ip_address('1.2.3.4'))\n", "ipaddress.ip_address is not supported"),
        "ip_network": ("import ipaddress\nprint(ipaddress.ip_network('1.2.3.0/24'))\n", "ipaddress.ip_network is not supported"),
        "IPv4Network": ("from ipaddress import IPv4Network\nprint(IPv4Network('1.2.3.0/24'))\n", "ipaddress.IPv4Network is not supported"),
        "IPv6Address": ("import ipaddress as ia\nprint(ia.IPv6Address('::1'))\n", "ipaddress.IPv6Address is not supported"),
        "IPv4Interface": ("import ipaddress\nprint(ipaddress.IPv4Interface('1.2.3.4/8'))\n", "ipaddress.IPv4Interface is not supported"),
        "is_private": ("import ipaddress\nprint(ipaddress.IPv4Address('10.0.0.1').is_private)\n", "ipaddress.is_private is not supported"),
        "is_global": ("from ipaddress import IPv4Address\nprint(IPv4Address('10.0.0.1').is_global)\n", "ipaddress.is_global is not supported"),
        "module as value": ("import ipaddress\nm = ipaddress\nprint(m.IPv4Address('1.2.3.4'))\n", "ipaddress used as a value"),
        "subclass": ("import ipaddress\nclass A(ipaddress.IPv4Address):\n    pass\nprint(A('1.2.3.4'))\n",
                     "a subclass of IPv4Address is not supported"),
        "star": ("from ipaddress import *\nprint(IPv4Address('1.2.3.4'))\n", "from ipaddress import *"),
        "name clash": ("import ipaddress\nclass AddressValueError(Exception):\n    pass\nprint(ipaddress.IPv4Address('1.2.3.4'))\n",
                       "binds the name AddressValueError itself"),
    }

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in self.CASES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, "refused")
                shown = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                self.assertIn(wanted, shown)
                self.assertIn("write instead:", shown)
                self.assertFalse(exe.exists())


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_ipaddress_keep_their_text(self):
        import stdlib5
        for text in ["# ipaddress only in a comment\nprint(1)\n", "s = 'import ipaddress'\nprint(s.upper())\n"]:
            notes = []
            self.assertEqual(stdlib5.rewrite_text(text, notes), text)
            self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
