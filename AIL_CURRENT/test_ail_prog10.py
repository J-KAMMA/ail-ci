"""The hot functions of the prog10 programs that now reach the typed path, against CPython 3.12.

`g25_030.find_completions` used to stop the typed path with "this use of a str as an iterable is not
built (plain `for c in s` is); for an index keep a counter". The typed emitter now builds
`for index, ch in enumerate(text)` as the same UTF-8 character walk as `for c in text`, with a private
counter so the index counts characters (not bytes) and a body that rebinds it cannot disturb the next
step. The whole `g25_030` program is typed now, as are the routes an iterable can take to the loop
(argument, list item, attribute, dict value). Both AIL_IR modes must print exactly what CPython prints.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT.parent / "lab" / "census" / "programs" / "gdev" / "g25_030.py"
HAVE_CC = shutil.which("gcc") is not None or shutil.which("cc") is not None

ENUMERATE_ROUTES = '''class Box:
    def __init__(self, text: str) -> None:
        self.text: str = text


def collect(text: str) -> list[int]:
    out: list[int] = []
    for index, ch in enumerate(text):
        if ch == "b":
            out.append(index)
        index = 999
    return out


def main() -> None:
    sources: list[str] = ["", "abb", "éabb", "aébb", "東京abb", "ababbxabbbabb"]
    for s in sources:
        print(collect(s))
    print(collect("ab" + "b"))
    print(collect(sources[2]))
    d: dict[str, str] = {"k": "aébb"}
    print(collect(d["k"]))
    b = Box("東京abb")
    print(collect(b.text))
    for i, ch in enumerate("aé日b"):
        print(i, ch)
    print(collect("e\\u0301abb"))
    print(collect("abb" * 3))


main()
'''


def compile_source(directory, source, name, ir):
    exe = Path(directory, name + "_" + ir)
    env = dict(os.environ, AIL_IR=ir, AIL_NO_CACHE="1")
    for key in ("AIL_NO_GENERAL", "AIL_UNIFIED_FORCE", "AIL_QUIET_FALLBACK"):
        env.pop(key, None)
    res = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                          "--syntax", "python", "-o", str(exe)],
                         cwd=directory, capture_output=True, text=True, timeout=1800, env=env)
    return res, exe


def run_cpython(directory, source, name):
    if isinstance(source, str) and "\n" in source:
        path = Path(directory, name + "_cpython.py")
        path.write_text(source, encoding="utf-8")
    else:
        path = Path(source)
    return subprocess.run([sys.executable, "-X", "utf8", str(path)], capture_output=True, timeout=300)


class Prog10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="prog10_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, source, name, ir):
        if isinstance(source, str):
            path = Path(self.tmp, name + ".py")
            path.write_text(source, encoding="utf-8")
            source = path
        res, exe = compile_source(self.tmp, source, name, ir)
        self.assertEqual(res.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                         % (name, ir, res.stdout[-2000:], res.stderr[-2000:]))
        self.assertNotIn("built on the general path", res.stderr,
                         "%s (AIL_IR=%s) fell back: %s" % (name, ir, res.stderr[-600:]))
        want = run_cpython(self.tmp, source, name)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        self.assertEqual(got.returncode, want.returncode,
                         "%s (AIL_IR=%s) exit %s against CPython's %s\n%s"
                         % (name, ir, got.returncode, want.returncode,
                            got.stderr.decode("utf-8", "replace")[-1000:]))
        self.assertEqual(got.stdout, want.stdout, name + " (AIL_IR=" + ir + ")")

    def test_g25_030_is_typed_and_matches_cpython(self):
        if not PROGRAM.is_file():
            self.skipTest("lab/census/programs/gdev/g25_030.py is not present")
        for ir in ("0", "1"):
            with self.subTest(ir=ir):
                self.check(PROGRAM, "g25_030", ir)

    def test_enumerate_str_routes_and_boundaries(self):
        for ir in ("0", "1"):
            with self.subTest(ir=ir):
                self.check(ENUMERATE_ROUTES, "enum_routes", ir)


if __name__ == "__main__":
    unittest.main()
