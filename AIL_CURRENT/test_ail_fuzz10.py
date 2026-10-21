"""fuzz10: f-strings and str.format, compared with CPython 3.12 on both builds.

Each program is built twice (the default build, and AIL_UNIFIED_FORCE=1's general path) and must
print what CPython prints. The three silent differences this round fixed:

1. The IR text lowerer dropped every part of a spec the small fmt_int/fmt_float helpers do not
   know -- a sign (+/space), '#', grouping, '=' alignment and the non-decimal int types -- so
   `f"{x:+d}"`, `f"{x:=08}"`, `f"{x:*=5}"` printed no sign / padded on the wrong side. Such a spec
   now leaves the IR function to the legacy path, whose ail_fmt_gen implements it.
2. The general path's runtime spec parser/padder (cruntime.py and safetyrt.py) did not recognize
   an explicit '=' alignment and did not treat a space sign as a sign when zero padding, so
   `f"{x: 010.2f}"` printed `00000 3.50` and `f"{x:=08}"` spaces; the '0' flag now zero-fills
   even next to an explicit alignment, unless a fill character was written.
3. The typed path's conversion handling: a bool reached through `for b in (True, False)` was not
   inferred as a bool (`!r`/`!s` printed 1/0), and `!s` with a format spec formatted the number
   instead of its text. A tuple of bools is now a bool sequence, and !s converts before the spec.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAMS = {}
PROGRAMS['sign_zero_int'] = r'''def main():
    for x in (0, 5, -5, 42, -42, True, False):
        print(f"[{x:+06}][{x: 06}][{x:-06}][{x:+6}][{x: 6}]")
        print(f"[{x:=08}][{x:*=+10}][{x:0=8}][{x:=^8}][{x:=<8}][{x:=>8}]")
        print(f"[{x:05}][{x:+05}][{x: 05}][{x:0=5}][{x:*=5}]")


main()
'''
PROGRAMS['sign_zero_float'] = r'''def main():
    for x in (0.0, -0.0, 3.5, -3.5, 1.25, -1.25):
        print(f"[{x:+010.2f}][{x: 010.2f}][{x:-010.2f}][{x:010.2f}][{x:+010}]")
        print(f"[{x:=010.2f}][{x:*=+12.2f}][{x:=^12.2f}][{x:0=10}]")
        print(f"[{x:*>10.2f}][{x:0<10.2f}][{x:^10.2f}][{x:*^11.2f}]")


main()
'''
PROGRAMS['int_specs'] = r'''def main():
    for x in (0, 7, 255, -255, 1234567):
        print(f"{x:x}|{x:X}|{x:#x}|{x:#X}|{x:o}|{x:#o}|{x:b}|{x:#b}|{x:08x}|{x:#010x}")
        print(f"{x:,}|{x:_}|{x:_x}|{x:+}|{x: }|{x:#08b}|{x:#08o}|{x:#08x}")


main()
'''
PROGRAMS['align_zero'] = r'''def main():
    for spec in ("<08", ">08", "^08", "=08", "*>08", "*<08", "*^08", "=8", "0=8", "*=8"):
        print(spec, f"[{5:{spec}}][{-5:{spec}}]")
    for spec in ("<08", ">08", "^08", "=08", "0=8", "*=10.2f", " 010.2f"):
        print(spec, f"[{3.5:{spec}}][{-3.5:{spec}}]")


main()
'''
PROGRAMS['bool_loop'] = r'''def main():
    for b in (True, False):
        print(f"[{b!r}][{b!s}][{b!r:>8}][{b!s:<8}]")
        print("[{!r}][{!s}][{!r:>8}][{!s:<8}]".format(b, b, b, b))
        print(f"[{b:d}][{b:b}][{b:#x}][{b:o}][{b:c}][{b:,}][{b:+d}]")


main()
'''
PROGRAMS['conversion_spec'] = r'''def main():
    for x in (5, 3.5, "ab", True, None):
        print(f"[{x!r}][{x!s}]")
        print("[{!r:>6}][{!s:<6}]".format(x, x))
    for s in ("a", "abc"):
        print(f"[{s!s:>6}][{s!r:>8}][{s!s:*^8.2}]")


main()
'''
PROGRAMS['nested_variables'] = r'''def main():
    w = 7
    p = 2
    x = 3.14159
    s = "ab"
    print(f"[{x:{w}}][{x:{w}.{p}f}][{x:>{w}.{p}}]")
    print(f"[{s:{w}}][{s:>{w}}][{s:*^{w}}]")
    print("[{x:{w}}][{x:{w}.{p}f}][{x:>{w}.{p}}]".format(x=x, w=w, p=p))
    print("[{0:{1}}][{0:{1}.{2}f}]".format(x, w, p))


main()
'''
PROGRAMS['nested_attr_list_dict'] = r'''class C:
    def __init__(self, w=6, p=2, spec=">7"):
        self.w = w
        self.p = p
        self.spec = spec
        self.v = 3.14159


def main():
    L = [7, 2]
    D = {"w": 5, "p": 3}
    c = C()
    print(f"[{'x':>{L[0]}}][{3.14159:{L[0]}.{L[1]}f}]")
    print("[{s:>{L[0]}}][{x:{L[0]}.{L[1]}f}]".format(s="x", x=3.14159, L=L))
    print(f"[{'x':>{D['w']}}][{3.14159:{D['w']}.{D['p']}f}]")
    print("[{s:>{D[w]}}][{x:{D[w]}.{D[p]}f}]".format(s="x", x=3.14159, D=D))
    print(f"[{'x':>{c.w}}][{c.v:{c.w}.{c.p}f}][{c.v:{c.spec}}]")
    print("[{0:>{1.w}}][{0:{1.w}.{1.p}f}][{0:{1.spec}}]".format("x", c))


main()
'''
PROGRAMS['escaped_braces'] = r'''def main():
    x = 5
    print(f"{{}} {x} {{x}} {{{{}}}}")
    print(f"a{{b}}c{x}d{{e}}")
    print(f"{{{{{x}}}}}")
    print(f"a{{{{b}}}}c{x}d{{{{e}}}}")
    print("{{}}".format())
    print("{{0}}".format(1))
    print("{{{0}}}".format(1))
    print("{{{0!r}}}".format("a"))
    print("a{{b}}c{0}d{{e}}".format(1))


main()
'''
PROGRAMS['width_precision_edges'] = r'''def main():
    for w in (-10, -5, -1, 0, 1, 5, 200):
        print(f"[{'ab':{w}}][{5:{w}}][{3.5:{w}.2f}]")
    for p in (0, 1, 2, 15, 20):
        print(f"[{'abcdef':.{p}}][{0.1:.{p}f}][{1e-20:.{p}}][{1e20:.{p}e}][{1.0:.{p}g}]")
    for w in (1, 2, 3, 4, 5, 10):
        print(f"[{'a':^{w}}][{'ab':^{w}}][{'abc':^{w}}]")


main()
'''
PROGRAMS['unicode_fill_precision'] = r'''def main():
    for fill in ("é", "日", "\u00b7"):
        for align in ("<", ">", "^"):
            print(f"[{'ab':{fill}{align}7}][{'abc':{fill}{align}7.2}]")
    for s in ("é", "éé", "日本語", "aé日"):
        print(f"[{s:.0}][{s:.1}][{s:.2}][{s:.3}][{s:*>6.2}]")


main()
'''
PROGRAMS['format_map_nested'] = r'''def main():
    d = {"a": 5, "b": 2, "w": 7}
    print("{a:>{w}}|{b:<{w}}|".format_map(d))
    print("{a:{w}.{b}f}|".format_map({"a": 3.14159, "b": 2, "w": 9}))
    d2 = {"a": 3.14159, "w": 9, "p": 2, "s": "*"}
    print("{a:{w}.{p}f}|".format_map(d2))
    print("{a:{s}^{w}.{p}f}|".format_map(d2))


main()
'''
PROGRAMS['none_and_group'] = r'''def main():
    v = None
    print(f"{v}|{v!r}|{v!s}")
    print("{}|{!r}|{!s}".format(v, v, v))
    for x in (0, 1234567, -1234567):
        print(f"{x:,}|{x:_}|{x:_x}|{x:,d}")
    for x in (0.0, 1234567.891, -1234567.891):
        print(f"{x:,.2f}|{x:_.2f}|{x:015,.2f}|{x:,.0f}")


main()
'''
PROGRAMS['positional_order'] = r'''def f(n):
    print("f", n)
    return n


def main():
    print("{1} {0} {1}".format(f(1), f(2)))
    print("{0}{0}{1}".format(f(3), f(4)))
    print("{1:>3}|{0:<3}|".format(f(5), f(6)))
    print("{b} {a}".format(a=f(7), b=f(8)))
    print("{0[0]}-{0[1]} {1[k]}".format([5, 6], {"k": "dv"}))


main()
'''
PROGRAMS['float_edges'] = r'''def main():
    for x in (0.0, -0.0, 1.0, 1.5, 100.0, 0.000012345, 12345.678, 1e22):
        print(f"{x}|{x:.0}|{x:.3}|{x:g}|{x:.3g}|{x:#.3g}|{x:e}|{x:.0e}|{x:%}|{x:.0%}")
    for x in (0.1, 1.0, 100000.0, 0.0001, 1e-5):
        for p in (0, 1, 2, 4):
            print(f"[{x:.{p}g}][{x:#.{p}g}][{x:.{p}G}]")


main()
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", CLI, "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory(prefix="ail-fuzz10-") as directory:
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


if __name__ == "__main__":
    unittest.main()
