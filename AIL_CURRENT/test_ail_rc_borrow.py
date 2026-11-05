"""rc2: borrow inference for read-only parameters.

A parameter that the callee only reads takes no `ail_obj_retain` on entry and no
`ail_obj_release` on exit; the caller keeps its reference alive across the call.  Four small
programs pin the rule down: a read-only helper and a recursive walk are borrowed, while a helper
that stores its argument and one that returns it stay owned.  Each is checked against CPython and
for the expected entry retain in `program.c`.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))

from ir import borrow  # noqa: E402


def build(directory, text, name):
    source = Path(directory, name + ".py")
    exe = Path(directory, name)
    debug = Path(directory, name + ".dbg")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text(encoding="utf-8")


def body_of(program, name):
    match = re.search(r"\n[\w *]+\b%s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


NODE = """
from __future__ import annotations


class Node:
    def __init__(self, value: int, next: Node | None) -> None:
        self.value: int = value
        self.next: Node | None = next
"""

READ_ONLY = NODE + """
def helper(n: Node) -> int:
    return n.value + 1


def main() -> int:
    a = Node(41, None)
    print(helper(a))
    return 0


main()
"""

RECURSIVE = NODE + """
def walk(n: Node | None) -> int:
    if n is None:
        return 0
    return n.value + walk(n.next)


def main() -> int:
    head = Node(1, Node(2, Node(3, None)))
    print(walk(head))
    return 0


main()
"""

STORES = NODE + """
def helper(items: list[Node], n: Node) -> int:
    items.append(n)
    return n.value


def main() -> int:
    items: list[Node] = []
    a = Node(7, None)
    print(helper(items, a))
    print(items[0].value)
    return 0


main()
"""

RETURNS = NODE + """
def helper(n: Node) -> Node:
    return n


def main() -> int:
    a = Node(9, None)
    print(helper(a).value)
    return 0


main()
"""


class BorrowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.cases = {}
        for name, text in (("read_only", READ_ONLY), ("recursive", RECURSIVE),
                           ("stores", STORES), ("returns", RETURNS)):
            cls.cases[name] = build(cls.directory.name, text, name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check(self, name):
        exe, program = self.cases[name]
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        expected = subprocess.run([sys.executable, str(Path(self.directory.name, name + ".py"))],
                                  capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)
        return program

    def test_read_only_helper_is_borrowed(self):
        self.check("read_only")
        self.assertEqual(body_of(self.cases["read_only"][1], "helper").count("ail_obj_retain("), 0)

    def test_recursive_walk_is_borrowed(self):
        self.check("recursive")
        body = body_of(self.cases["recursive"][1], "walk")
        self.assertEqual(body.count("ail_obj_retain("), 0)
        self.assertNotIn("ail_obj_release(v_n)", body)

    def test_storing_helper_takes_a_reference_at_the_store(self):
        self.check("stores")
        body = body_of(self.cases["stores"][1], "helper")
        self.assertIn("ail_obj_store_Node(&v__t2, v_n, 0)", body)
        self.assertEqual(body.count("ail_obj_retain("), 0)
        self.assertNotIn("ail_obj_retain(v_items)", body)

    def test_returning_helper_keeps_the_retain(self):
        self.check("returns")
        body = body_of(self.cases["returns"][1], "helper")
        self.assertEqual(body.count("ail_obj_retain("), 1)

    def test_switch_turns_elision_off(self):
        text = (Path(self.directory.name, "read_only.py").read_text(encoding="utf-8"))
        env = dict(os.environ, AIL_RC_BORROW="0")
        debug = Path(self.directory.name, "off.dbg")
        source = Path(self.directory.name, "off.py")
        source.write_text(text, encoding="utf-8")
        built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile",
                                str(source), "-o", str(Path(self.directory.name, "off")),
                                "--debug-dir", str(debug)],
                               capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        program = (debug / "program.c").read_text(encoding="utf-8")
        self.assertIn("ail_obj_retain(v_n)", body_of(program, "helper"))


class AnalysisTests(unittest.TestCase):
    def sets(self, text):
        import ast
        return borrow.analyze(ast.parse(text), False, {"main"})

    def test_rule(self):
        self.assertEqual(sorted(self.sets(READ_ONLY)["helper"]), ["n"])
        self.assertEqual(sorted(self.sets(RECURSIVE)["walk"]), ["n"])
        self.assertEqual(sorted(self.sets(STORES)["helper"]), ["items"])
        self.assertEqual(sorted(self.sets(RETURNS).get("helper", ())), [])

    def test_switch(self):
        self.assertTrue(borrow.enabled())


if __name__ == "__main__":
    unittest.main()
