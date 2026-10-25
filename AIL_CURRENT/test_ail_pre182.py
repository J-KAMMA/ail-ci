"""Pre-182: bytes/bytearray padding names the fillchar type like CPython.

`ljust`, `rjust` and `center` converted the fillchar with the generic bytes helper
first, so a str, int, bool or other non-bytes fillchar raised ``a bytes-like object
is required`` instead of CPython's ``<method>() argument 2 must be a byte string of
length 1, not <type>``.  None was already special-cased by fuzz51.  The type check
now happens before the conversion, and bytes/bytearray fillchars of the wrong length
still name their own type.  The program exercises the value directly, through an
argument, a list item, an attribute and a dict value, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class C:
    pass


def show(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except TypeError as e:
        print(label, "TypeError", str(e))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def call(method: int, s, w: int, fill):
    if method == 0:
        return s.ljust(w, fill)
    if method == 1:
        return s.rjust(w, fill)
    return s.center(w, fill)


def main() -> None:
    obj = C()
    items = [None, "x", 1, True, b"", b"ab", bytearray(b""), bytearray(b"ab"), b"#", bytearray(b"#")]
    attr = C()
    attr.fill = None
    d = {"none": None, "str": "x", "int": 1, "bytes": b"ab", "ba": bytearray(b"ab"), "ok": b"#"}
    for fill in items:
        show("bl_%s" % type(fill).__name__, lambda fill=fill: b"abc".ljust(5, fill))
        show("br_%s" % type(fill).__name__, lambda fill=fill: b"abc".rjust(5, fill))
        show("bc_%s" % type(fill).__name__, lambda fill=fill: b"abc".center(6, fill))
    show("obj", lambda: b"abc".ljust(5, obj))
    show("arg_none", lambda: call(0, b"abc", 5, None))
    show("arg_str", lambda: call(1, b"abc", 5, "x"))
    show("arg_int", lambda: call(2, bytearray(b"abc"), 6, 1))
    show("list_none", lambda: b"abc".ljust(5, items[0]))
    show("list_str", lambda: b"abc".rjust(5, items[1]))
    show("list_int", lambda: b"abc".center(6, items[2]))
    show("list_empty_bytes", lambda: b"abc".ljust(5, items[4]))
    show("list_ok_ba", lambda: bytearray(b"abc").center(6, items[9]))
    show("attr_none", lambda: b"abc".ljust(5, attr.fill))
    attr.fill = "y"
    show("attr_str", lambda: b"abc".rjust(5, attr.fill))
    attr.fill = 2
    show("attr_int", lambda: b"abc".center(6, attr.fill))
    show("dict_none", lambda: b"abc".ljust(5, d["none"]))
    show("dict_str", lambda: b"abc".rjust(5, d["str"]))
    show("dict_int", lambda: b"abc".center(6, d["int"]))
    show("dict_bytes", lambda: b"abc".ljust(5, d["bytes"]))
    show("dict_ba", lambda: b"abc".rjust(5, d["ba"]))
    show("dict_ok", lambda: b"abc".center(6, d["ok"]))
    show("default_l", lambda: b"abc".ljust(5))
    show("default_r", lambda: bytearray(b"abc").rjust(6))
    show("default_c", lambda: b"abc".center(6))
    for w in (-1, 0, 2, 3, 5, 6):
        show("width_%d" % w, lambda w=w: b"abc".ljust(w, None))
        show("width_ok_%d" % w, lambda w=w: b"abc".rjust(w, b"#"))
        show("width_ba_%d" % w, lambda w=w: bytearray(b"abc").center(w, bytearray(b"#")))
    show("empty_none", lambda: b"".ljust(3, None))
    show("empty_ok", lambda: b"".center(3, b"#"))
    show("str_none", lambda: "abc".ljust(5, None))
    show("str_center_none", lambda: "abc".center(5, None))
    print("done")


main()
'''


class Pre182Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre182-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self):
        path = self.dir / "probe_cpython.py"
        path.write_text(PROGRAM, encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(path)], cwd=self.dir,
                              capture_output=True, timeout=120,
                              env=dict(os.environ, PYTHONUTF8="1"))

    def build_and_run(self, general):
        path = self.dir / "probe.py"
        path.write_text(PROGRAM, encoding="utf-8")
        exe = self.dir / ("exe_probe" + ("_g" if general else "_d"))
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        env.pop("AIL_NO_GENERAL", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        built = subprocess.run([sys.executable, "-B", CLI, "compile", path.name,
                                "--syntax", "python", "-o", exe.name],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)

    def test_fillchar_type_and_length_on_both_builds(self):
        want = self.cpython()
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            got = self.build_and_run(general)
            self.assertEqual(got.returncode, 0,
                             got.stderr.decode("utf-8", "replace")[-2000:])
            self.assertEqual(got.stdout, want.stdout,
                             "general=%s\n%s" % (general, got.stderr.decode("utf-8", "replace")[-2000:]))


if __name__ == "__main__":
    unittest.main()
