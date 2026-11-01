"""fnmatch on the general path (stdtop.py + prelude_fnmatch.py), compared with CPython 3.12.

* the prelude runs under CPython next to fnmatch: generated patterns and names (str and bytes, the empty string,
  brackets, ranges, negations, escapes and the translate-only edge cases) must give the same match, the same
  translated regexp, the same filtered list and the same exception class and text;
* every program in lab/stdlib/fnmatch is compiled with the default build and with AIL_UNIFIED_FORCE=1 and must
  print the same bytes as CPython, with the same exit status.
"""
import fnmatch
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
REPO = ROOT.parent
LAB = REPO / "lab" / "stdlib" / "fnmatch"
for each in (str(PKG), str(ROOT)):
    if each not in sys.path:
        sys.path.insert(0, each)


def attempt(f):
    try:
        return ("ok", f())
    except Exception as e:
        return ("err", type(e).__name__, str(e))


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


PATTERN_ALPHABET = "abcABC012[]!^-*?\\/.+()&~| \t\n"
NAME_ALPHABET = "abcABC012[]!^-*?\\/. \t\n"


class Prelude(unittest.TestCase):
    def test_translate(self):
        import prelude_fnmatch as P
        rnd = random.Random(42)
        patterns = ["", "*", "**", "a*b*c", "[", "[]", "[]]", "[!]", "[!]]", "[-a]", "[a-]", "[a-z-]", "[^a]",
                    "[!a-z]", "[a-\\]", "a[b", "a]b", r"a\*b", "[--0]", "[z-a]", "[&&]", "x[~a]?*"]
        patterns += ["".join(rnd.choice(PATTERN_ALPHABET) for _ in range(rnd.randint(0, 14))) for _ in range(4000)]
        for pat in patterns:
            self.assertEqual(attempt(lambda: P._ail_fnmatch_translate(pat)), attempt(lambda: fnmatch.translate(pat)),
                             repr(pat))
        for pat in [b"", b"*", b"*.py", b"[!a]", [1], ["a"]]:
            self.assertEqual(attempt(lambda: P._ail_fnmatch_translate(pat)), attempt(lambda: fnmatch.translate(pat)),
                             repr(pat))
        for bad in [5, None, 1.5, object()]:
            self.assertEqual(attempt(lambda: P._ail_fnmatch_translate(bad)),
                             attempt(lambda: fnmatch.translate(bad)), repr(bad))

    def test_matching(self):
        import prelude_fnmatch as P
        rnd = random.Random(7)
        for prefix in ("", "app-", "x", "backup-"):
            for _ in range(5000):
                pat = "".join(rnd.choice(PATTERN_ALPHABET) for _ in range(rnd.randint(0, 14)))
                name = prefix + "".join(rnd.choice(NAME_ALPHABET) for _ in range(rnd.randint(0, 12)))
                self.assertEqual(attempt(lambda: P._ail_fnmatch_case(name, pat)),
                                 attempt(lambda: fnmatch.fnmatchcase(name, pat)), (name, pat))
                self.assertEqual(attempt(lambda: P._ail_fnmatch_fn(name, pat)),
                                 attempt(lambda: fnmatch.fnmatch(name, pat)), (name, pat))
                bytes_pat = pat.encode()
                bytes_name = name.encode()
                self.assertEqual(attempt(lambda: P._ail_fnmatch_case(bytes_name, bytes_pat)),
                                 attempt(lambda: fnmatch.fnmatchcase(bytes_name, bytes_pat)), (name, pat))
                self.assertEqual(attempt(lambda: P._ail_fnmatch_fn(bytes_name, bytes_pat)),
                                 attempt(lambda: fnmatch.fnmatch(bytes_name, bytes_pat)), (name, pat))

    def test_filter(self):
        import prelude_fnmatch as P
        rnd = random.Random(11)
        names = ["app-1.4.2.tar.gz", "app-1.4.2-py3-none-any.whl", "README.md", "CHANGELOG", "", "a b",
                 "line\nbreak", "service.log.10", "service.log.gz", "backup-a.1", "__pycache__"]
        names += ["".join(rnd.choice(NAME_ALPHABET) for _ in range(rnd.randint(0, 10))) for _ in range(200)]
        patterns = ["", "*", "?", "*.py", "*.tar.gz", "*sha256", "app-*", "[abc]*", "[!a]*", "[]]", "*\n*",
                    "service.log.[0-9]*", "**/*"]
        patterns += ["".join(rnd.choice(PATTERN_ALPHABET) for _ in range(rnd.randint(0, 10))) for _ in range(500)]
        for pat in patterns:
            self.assertEqual(attempt(lambda: P._ail_fnmatch_filter(names, pat)),
                             attempt(lambda: fnmatch.filter(names, pat)), repr(pat))
            bnames = [name.encode() for name in names[:20]]
            bpat = pat.encode()
            self.assertEqual(attempt(lambda: P._ail_fnmatch_filter(bnames, bpat)),
                             attempt(lambda: fnmatch.filter(bnames, bpat)), repr(pat))
        for names_arg, pat in [(None, "*"), (5, "*"), (["a", 5], "*"), ([b"a", "a"], "*"), ("abc", "*"),
                               ([], "*"), ([], b"*"), (None, b"*")]:
            self.assertEqual(attempt(lambda: P._ail_fnmatch_filter(names_arg, pat)),
                             attempt(lambda: fnmatch.filter(names_arg, pat)), (names_arg, pat))

    def test_bad_arguments(self):
        import prelude_fnmatch as P
        values = [None, 5, 1.5, b"a", bytearray(b"a"), ["x"], ("a",), {"a": 1}, True]
        for name in values:
            for pat in values + ["*", b"*"]:
                self.assertEqual(attempt(lambda: P._ail_fnmatch_fn(name, pat)),
                                 attempt(lambda: fnmatch.fnmatch(name, pat)), (name, pat))
                self.assertEqual(attempt(lambda: P._ail_fnmatch_case(name, pat)),
                                 attempt(lambda: fnmatch.fnmatchcase(name, pat)), (name, pat))


class CompiledPrograms(unittest.TestCase):
    def test_lab_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest("lab/stdlib/fnmatch is not part of this tree")
        programs = sorted(LAB.glob("*.py"))
        self.assertGreaterEqual(len(programs), 12)
        for path in programs:
            text = path.read_text(encoding="utf-8")
            for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
                with self.subTest(program=path.name, env=env), tempfile.TemporaryDirectory() as directory:
                    built, source, exe = compile_python(directory, text, path.stem, **env)
                    self.assertEqual(built.returncode, 0, "%s %r\n%s%s" % (path.name, env, built.stdout, built.stderr))
                    want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True,
                                          timeout=120)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120)
                    self.assertEqual(got.returncode, want.returncode,
                                     "%s %r\n%s" % (path.name, env, got.stderr[-500:]))
                    self.assertEqual(got.stdout, want.stdout, "%s %r" % (path.name, env))


if __name__ == "__main__":
    unittest.main()
