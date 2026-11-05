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
        # `n` is stored into `items`, so it is not borrowed: one entry retain, and the store holds
        # its own reference too.  The list `items` is only read and stays borrowed.
        self.assertEqual(body.count("ail_obj_retain("), 1)
        self.assertNotIn("ail_obj_retain(v_items)", body)

    def test_returning_helper_keeps_the_retain(self):
        self.check("returns")
        body = body_of(self.cases["returns"][1], "helper")
        # `n` is returned, so it is owned: the entry retain and the retain that hands the value to
        # the caller.  (The rule refuses it; the returned reference is still correct.)
        self.assertEqual(body.count("ail_obj_retain("), 2)

    def test_switch_is_the_escape_hatch(self):
        """`AIL_RC_BORROW=0` turns the elision off: the read-only helper keeps its entry retain.
        (The pre-rc2 ad-hoc scan would also have borrowed it; the default build uses the new rule,
        whose difference from that scan is pinned by the storing-helper test above.)"""
        text = Path(self.directory.name, "read_only.py").read_text(encoding="utf-8")
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

    def test_comprehension_stores_are_refused(self):
        """A comprehension builds a new container and stores the element in it, so the element is
        not read-only (`return [p for _ in range(2)]` is a store, not a read)."""
        node = """
from __future__ import annotations


class Node:
    def __init__(self, value: int, next: Node | None) -> None:
        self.value: int = value
        self.next: Node | None = next


def wrap(p: Node) -> list[Node]:
    return [p for _ in range(2)]


def hold(p: Node) -> int:
    ys = [p for _ in range(3)]
    return len(ys)


def pack(p: Node, n: int) -> list[Node]:
    d = {i: p for i in range(n)}
    return [d[0], d[n - 1]]


def main() -> int:
    return 0


main()
"""
        sets = self.sets(node)
        self.assertNotIn("p", sets.get("wrap", ()))
        self.assertNotIn("p", sets.get("hold", ()))
        self.assertNotIn("p", sets.get("pack", ()))
        # the comprehension's iterable is read, and `n` is only used there
        self.assertIn("n", sets.get("pack", ()))

    def test_container_literals_are_stores(self):
        """A container literal stores its elements wherever it appears, not only as an assignment
        value: `for q in [p, p]` keeps a reference to `p`, so `p` is not read-only."""
        node = """
from __future__ import annotations


class Node:
    def __init__(self, value: int) -> None:
        self.value: int = value


def scan(p: Node, n: int) -> int:
    total = 0
    for q in [p, p]:
        total += q.value
    return total + n


def either(p: Node, n: int) -> int:
    return p.value if n else 0


def main() -> int:
    return 0


main()
"""
        sets = self.sets(node)
        self.assertNotIn("p", sets.get("scan", ()))
        self.assertIn("p", sets.get("either", ()))

    def test_methods_are_analysed(self):
        """A class body is a scope: a method's read-only parameters are borrowed and one stored
        into a field is refused.  `self` is a parameter like any other at analysis time."""
        node = """
from __future__ import annotations


class Node:
    def __init__(self, value: int) -> None:
        self.value: int = value


class Box:
    def __init__(self, k: int) -> None:
        self.k: int = k
        self.held: Node | None = None

    def weigh(self, p: Node) -> int:
        return self.k * p.value

    def hold(self, p: Node) -> int:
        self.held = p
        return p.value


def main() -> int:
    return 0


main()
"""
        sets = self.sets(node)
        self.assertIn("p", sets.get("weigh", ()))
        self.assertNotIn("p", sets.get("hold", ()))

    def test_switch(self):
        self.assertTrue(borrow.enabled())


class VerifyTests(unittest.TestCase):
    def test_borrowed_store_is_an_error(self):
        """The IR verifier rejects an owning store of a borrowed parameter (OSSA's rule)."""
        from ir import verify
        from ir import ir as I
        p = I.Value(I.I64, hint="p")
        fn = I.Function("f", [p], ["p"], [I.I64], I.Region(), attrs={"borrow": ["p"]})
        fn.body.instrs.append(I.Instr("list.push", [p, p]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertTrue(checker.errors)

    def test_container_operand_is_not_a_store(self):
        """Writing through a borrowed container (`xs.append(v)`) reads that reference; only the
        value operand hands a reference on."""
        from ir import verify
        from ir import ir as I
        owner = I.Value(I.I64, hint="xs")
        value = I.Value(I.I64, hint="v")
        fn = I.Function("f", [owner, value], ["xs", "v"], [I.I64], I.Region(),
                        attrs={"borrow": ["xs"]})
        fn.body.instrs.append(I.Instr("list.push", [owner, value]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertFalse(checker.errors)

    def test_storing_a_borrowed_value_is_an_error(self):
        from ir import verify
        from ir import ir as I
        owner = I.Value(I.I64, hint="xs")
        value = I.Value(I.I64, hint="v")
        fn = I.Function("f", [owner, value], ["xs", "v"], [I.I64], I.Region(),
                        attrs={"borrow": ["v"]})
        fn.body.instrs.append(I.Instr("list.push", [owner, value]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertTrue(checker.errors)

    def test_local_store_is_not_an_escape(self):
        """An IR `store` initialises a local slot; it does not hand the reference on."""
        from ir import verify
        from ir import ir as I
        p = I.Value(I.I64, hint="p")
        place = I.Value(I.place(I.I64))
        fn = I.Function("f", [p], ["p"], [I.I64], I.Region(), attrs={"borrow": ["p"]})
        fn.body.instrs.append(I.Instr("store", [place, p]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertFalse(checker.errors)

    def test_region_yield_is_not_an_escape(self):
        """A region result (`yield` inside an `if`) hands the value to the enclosing region, not to
        the caller; Python generators are refused by the lowering, so it is never an escape."""
        from ir import verify
        from ir import ir as I
        p = I.Value(I.I64, hint="p")
        cond = I.Value(I.I1, hint="c")
        fn = I.Function("f", [p, cond], ["p", "c"], [I.I64], I.Region(),
                        attrs={"borrow": ["p"]})
        fn.body.instrs.append(I.Instr("if", [cond], regions=[
            I.Region(instrs=[I.Instr("yield", [p])]),
            I.Region(instrs=[I.Instr("yield", [p])])]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertFalse(checker.errors)

    def test_borrowed_return_is_an_error(self):
        from ir import verify
        from ir import ir as I
        p = I.Value(I.I64, hint="p")
        fn = I.Function("f", [p], ["p"], [I.I64], I.Region(), attrs={"borrow": ["p"]})
        fn.body.instrs.append(I.Instr("return", [p]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertTrue(checker.errors)

    def test_no_borrowed_params_is_clean(self):
        from ir import verify
        from ir import ir as I
        p = I.Value(I.I64, hint="p")
        fn = I.Function("g", [p], ["p"], [I.I64], I.Region())
        fn.body.instrs.append(I.Instr("return", [p]))
        checker = verify._Checker(fn, None, "S1")
        checker.check_borrowed()
        self.assertFalse(checker.errors)


if __name__ == "__main__":
    unittest.main()
