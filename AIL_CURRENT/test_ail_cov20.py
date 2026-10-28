"""Coverage cov20: `ranked = sorted(d.items(), ...)` walked in slices and `dict(sorted(d.items()))`,
each compared with CPython 3.12 on the general path and the default build.

The lowering runs only when the plain compile refuses the program. A name bound to
`sorted(d.items())` is supported when it is a plain function-local snapshot whose only later reads
are the iterable of `for k, v in ranked` or a slice of it; a rebinding, a nested scope, a `del` or
a conditional binding is refused by name rather than run with the wrong pairs.
"""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import sortkeys


PROGRAMS = {}
PROGRAMS['ranked'] = r'''def show(counts):
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for k, v in ranked[:3]:
        print(k, v)
    for k, v in ranked:
        print("all", k, v)
    for k, v in ranked[1:]:
        print("tail", k, v)
    for k, v in ranked[::-1]:
        print("rev", k, v)
    plain = sorted(counts.items())
    for k, v in plain:
        print("plain", k, v)


def main():
    text = "b a c b a b d"
    counts = {}
    for word in text.split():
        counts[word] = counts.get(word, 0) + 1
    show(counts)
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    for k, v in top[:2]:
        print("top", k, v)
    empty = {}
    nothing = sorted(empty.items(), key=lambda kv: kv[1])
    for k, v in nothing[:3]:
        print(k, v)
    ranked = sorted(counts.items(), key=lambda kv: kv[1])
    counts["a"] = 99
    counts["z"] = 0
    del counts["b"]
    for k, v in ranked:
        print("snapshot", k, v)


main()
'''
PROGRAMS['dictsorted'] = r'''def main():
    d = {"b": 2, "a": 1, "d": 4, "c": 3}
    print(dict(sorted(d.items())))
    print(dict(sorted(d.items(), reverse=True)))
    empty = {}
    print(dict(sorted(empty.items())))
    nums = {3: "c", 1: "a", 2: "b"}
    print(dict(sorted(nums.items())))
    flags = {True: "t", False: "f"}
    print(dict(sorted(flags.items())))
    mixed = {"z": [], "a": {}, "m": 0}
    print(dict(sorted(mixed.items())))


main()
'''

SAFE = '''def main():
    d = {"a": 2, "b": 1}
    ranked = sorted(d.items(), key=lambda kv: kv[1])
    for k, v in ranked[:1]:
        print(k, v)

main()
'''
UNSAFE = {
    'reassigned': '''def main():
    d = {"a": 1}
    ranked = sorted(d.items())
    ranked = [("x", 0)]
    for k, v in ranked:
        print(k, v)

main()
''',
    'nested': '''def main():
    d = {"a": 1}
    ranked = sorted(d.items())
    def show():
        for k, v in ranked:
            print(k, v)
    show()

main()
''',
    'conditional': '''def main():
    d = {"a": 1}
    if d:
        ranked = sorted(d.items())
    for k, v in ranked:
        print(k, v)

main()
''',
}


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                            source.name, "--syntax", "python", "-o", exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                  timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0,
                             "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
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


class Refused(unittest.TestCase):
    def refused(self, text, word, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_non_constant_reverse(self):
        source = ('def main():\n    d = {"a": 1, "b": 2}\n    f = True\n'
                  '    ranked = sorted(d.items(), reverse=f)\n'
                  '    for k, v in ranked:\n        print(k, v)\n\nmain()\n')
        self.refused(source, "reverse=", AIL_UNIFIED_FORCE="1")
        self.refused(source, "reverse=")


class LoweringBoundary(unittest.TestCase):
    def rewrite(self, text):
        tree = ast.parse(text)
        return sortkeys.rewrite(tree, 1, lambda key: False, Exception)

    def test_snapshot_is_lowered(self):
        self.assertEqual(self.rewrite(SAFE), 2)

    def test_not_a_plain_snapshot_is_refused_by_name(self):
        for label, text in UNSAFE.items():
            with self.subTest(case=label):
                with self.assertRaises(Exception) as caught:
                    self.rewrite(text)
                self.assertIn('sorted(d.items()) bound to a name', str(caught.exception))


if __name__ == "__main__":
    unittest.main()
