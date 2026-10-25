"""Pre-198: iterator and NotImplemented fillchar type names.

`bytes.ljust`/`rjust`/`center` name the failing fillchar's type in their TypeError.
The prelude reads it through `type(fillchar).__name__`, which lowered every iterator
to `iterator` and the hidden NotImplemented class to `_AilNotImplementedType`.
CPython names the concrete iterator class (`list_iterator`, `enumerate`, `zip`, ...)
and `NotImplementedType`.  The program exercises the values directly, through an
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

PROGRAM = r'''class Box:
    pass


def show(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def fill(value):
    return b"abc".ljust(5, value)


def name(value):
    return type(value).__name__


def main() -> None:
    h = {1: 2}
    items = [
        iter([]),
        iter((1,)),
        iter("ab"),
        iter(""),
        iter("é"),
        iter(h),
        iter(h.values()),
        iter(h.items()),
        iter({1}),
        iter(range(2)),
        iter(b"abc"),
        iter(b""),
        iter(bytearray(b"abc")),
        iter(bytearray(b"abcd")[1:3]),
        reversed([1]),
        reversed((1,)),
        reversed("ab"),
        reversed(range(2)),
        enumerate([1]),
        zip([1], [2]),
        map(str, [1]),
        filter(None, [1]),
        NotImplemented,
    ]
    for value in items:
        show("name_" + name(value), lambda value=value: name(value))
        show("fill_" + name(value), lambda value=value: fill(value))
    box = Box()
    box.fill = iter([])
    d = {}
    d["iter"] = iter([1])
    d["ni"] = NotImplemented
    show("arg_iter", lambda: fill(iter([])))
    show("arg_ni", lambda: fill(NotImplemented))
    show("list_iter", lambda: fill(items[0]))
    show("list_ni", lambda: fill(items[-1]))
    show("attr_iter", lambda: fill(box.fill))
    show("dict_iter", lambda: fill(d["iter"]))
    show("dict_ni", lambda: fill(d["ni"]))
    print("done")


main()
'''


class Pre198Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre198-")
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

    def test_iterator_and_notimplemented_type_names_on_both_builds(self):
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
