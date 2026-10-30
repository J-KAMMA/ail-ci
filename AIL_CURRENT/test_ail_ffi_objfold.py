"""An `@extern` program is linked through `link_objects`, which builds with the typed `to_c(strict=True)` and has no general-path
fallback. That path lacked the big-int gates of the plain typed-only build, so constant folding let `print(-2**63-1)` print
9223372036854775807 (INT64_MAX) silently. Every program here is built with the FFI stubs and compared with CPython: it must
print what CPython prints, or stop loudly at run time (`integer overflow`, exit 1, nothing printed), or be refused at compile
time by name. `SILENT` names the cases that used to differ."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_ail_ffi import CC, build_tiny, compile_cli, run_cpython

HEAD = '''from ail_ffi import *

@extern(lib="./libtiny.so", header="tiny.h")
def tiny_add(a: c_int, b: c_int) -> c_int: ...

def main():
'''

# (body of main, outcome): "same" = must print what CPython prints; "refuse" = compile-time refusal naming int64;
# "stop" = built, then stops at run time with `integer overflow` (exit 1, stdout empty); "refuse-or-stop" = either.
CASES = [
    ("print(-2**63-1)", "refuse"),                       # was: 9223372036854775807
    ("print(-2**63-2)", "refuse"),
    ("print(2**63)", "refuse"),
    ("print(-(-2**63))", "refuse"),
    ("print(9223372036854775808)", "refuse"),
    ("print(-9223372036854775809)", "refuse"),
    ("print(2**64)", "refuse"),
    ("print(1<<64)", "refuse-or-stop"),
    ("print(1<<63)", "refuse-or-stop"),
    ("print(2**62*4)", "refuse-or-stop"),
    ("print(3037000500*3037000500)", "refuse-or-stop"),
    ("print((1<<62)+(1<<62))", "refuse-or-stop"),
    ("x = 9223372036854775807\n    print(x+1)", "stop"),
    ("x = 9223372036854775807\n    print(x*2)", "stop"),
    ("x = -9223372036854775807-1\n    print(x-1)", "stop"),
    ("x = -9223372036854775807-1\n    print(-x)", "stop"),
    ("x = -9223372036854775807-1\n    print(x*-1)", "stop"),
    ("x = -9223372036854775807-1\n    print(abs(x))", "refuse-or-stop"),
    ("x = 64\n    print(1<<x)", "refuse-or-stop"),
    ("x = 63\n    print(1<<x)", "refuse-or-stop"),
    ("print(-2**63)", "same"),
    ("print(2**63-1)", "same"),
    ("print(-9223372036854775807-1)", "same"),
    ("print(9223372036854775807)", "same"),
    ("print(-9223372036854775808)", "same"),
    ("print(-2**63+1)", "same"),
    ("print(1<<62)", "same"),
    ("x = 9223372036854775806\n    print(x+1)", "same"),
    ("print(tiny_add(2, 3) + 2**40)", "same"),
]


@unittest.skipUnless(CC, "installed C compiler required")
class ObjectLinkFoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-objfold-")
        cls.dir = Path(cls.temp.name)
        build_tiny(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, index, body, outcome, typed_only):
        lines = body.split("\n")
        text = HEAD + "".join(("    " + l.lstrip(" ") if i == 0 else "    " + l.lstrip(" ")) + "\n" for i, l in enumerate(lines)) + "\nmain()\n"
        name = "p%d%s" % (index, "t" if typed_only else "g")
        path = name + ".py"
        (self.dir / path).write_text(text, encoding="utf8")
        expected = run_cpython(self.dir, path)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        label = "%r (typed-only=%s)" % (body, typed_only)
        env_before = os.environ.get("AIL_NO_GENERAL")
        try:
            if typed_only:
                built, exe = compile_cli(self.dir, path, name=name + ".out")
            else:
                os.environ.pop("AIL_NO_GENERAL", None)
                built, exe = self.compile_general(path, name + ".out")
        finally:
            if env_before is not None:
                os.environ["AIL_NO_GENERAL"] = env_before
        if built.returncode:
            self.assertIn(outcome, ("refuse", "refuse-or-stop"), label + " refused: " + built.stderr[-400:])
            self.assertTrue("int64" in built.stderr or "64-bit" in built.stderr, label + ": " + built.stderr[-400:])
            self.assertFalse(exe.exists(), label)
            return
        self.assertNotEqual(outcome, "refuse", label + " was built; CPython prints " + expected.stdout)
        ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
        if outcome == "same":
            self.assertEqual((ran.stdout, ran.returncode), (expected.stdout, 0), label + ran.stderr)
        else:
            self.assertEqual(ran.returncode, 1, label + " printed " + repr(ran.stdout))
            self.assertEqual(ran.stdout, "", label)
            self.assertIn("integer overflow", ran.stderr, label)

    def compile_general(self, path, name):
        import sys
        from test_ail_ffi import CLI, ROOT
        out = self.dir / name
        if out.exists():
            out.unlink()
        env = dict(os.environ, AIL_IR="0", PYTHONPATH=str(ROOT))
        env.pop("AIL_NO_GENERAL", None)
        done = subprocess.run([sys.executable, "-B", CLI, "compile", path, "-o", str(out)], cwd=self.dir,
                              capture_output=True, text=True, timeout=600, env=env)
        return done, out

    def test_typed_only_build(self):
        for index, (body, outcome) in enumerate(CASES):
            with self.subTest(body=body):
                self.check(index, body, outcome, True)

    def test_default_build(self):
        for index, (body, outcome) in enumerate(CASES):
            with self.subTest(body=body):
                self.check(index, body, outcome, False)


if __name__ == "__main__":
    unittest.main()
