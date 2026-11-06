"""rc3: cursor inference for loop traversal variables.

A local whose every binding is a read out of another object (a field read `n = n.next`, an
element read, or a parameter) and which is never stored, returned or captured is a *cursor*:
the owner it was read from keeps the object alive, so it takes no retain and no release.

Two accepted walks (a parameter cursor and a local cursor started from a borrowed parameter),
a walk that calls a pure reader (the callee's `ir/effects.py` summary has no write), and three
refused ones (the owner list is cleared, the field is reassigned, the cursor is appended to a
list) pin the rule down.  Each accepted program is run against CPython; each checks the
generated C for the absent store helper.  A call that writes the traversed field refuses the
cursor (`WRITER_CALL`).
"""
import ast
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

PARAM_CURSOR = NODE + """
def total(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc += n.value
        n = n.next
    return acc


def main() -> int:
    head = Node(1, Node(2, Node(3, None)))
    print(total(head))
    return 0


main()
"""

LOCAL_CURSOR = NODE + """
def total(head: Node | None) -> int:
    n = head
    acc = 0
    while n is not None:
        acc += n.value
        n = n.next
    return acc


def main() -> int:
    head = Node(4, Node(5, Node(6, None)))
    print(total(head))
    return 0


main()
"""

# 1. the owner list is cleared inside the loop: the elements it holds can be released, so the
#    element cursor would dangle.
CLEARED = NODE + """
def scan(items: list[Node]) -> int:
    acc = 0
    for item in items:
        acc += item.value
        items.clear()
    return acc


def main() -> int:
    items: list[Node] = [Node(7, None)]
    print(scan(items))
    return 0


main()
"""

# 2. the field the cursor came from is reassigned inside the loop: `n.next` no longer holds the
#    node the loop is walking.
FIELD_WRITTEN = NODE + """
def total(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc += n.value
        n.next = None
        n = n.next
    return acc


def main() -> int:
    head = Node(8, Node(9, None))
    print(total(head))
    return 0


main()
"""

# 4. the walk calls a pure reader: the callee's effect summary has no write, so the chain the
#    cursor walks cannot be released while it is live -- the cursor is accepted.
READER_CALL = NODE + """
def score(n: Node) -> int:
    return n.value


def total(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc += score(n)
        n = n.next
    return acc


def main() -> int:
    head = Node(1, Node(2, Node(3, None)))
    print(total(head))
    return 0


main()
"""

# 5. the walk calls a function that writes the traversed field: the effect summary names
#    `Field(?,next)`, so the keep-alive proof fails and the cursor stays owning.
WRITER_CALL = NODE + """
def cut(n: Node) -> int:
    n.next = None
    return n.value


def total(n: Node | None) -> int:
    acc = 0
    while n is not None:
        acc += cut(n)
        n = n.next
    return acc


def main() -> int:
    head = Node(4, Node(5, None))
    print(total(head))
    return 0


main()
"""

# 3. the cursor is appended to a list: the list keeps its own reference, which the cursor does
#    not own.
APPENDED = NODE + """
def collect(n: Node | None, out: list[Node]) -> int:
    acc = 0
    while n is not None:
        out.append(n)
        acc += n.value
        n = n.next
    return acc


def main() -> int:
    out: list[Node] = []
    head = Node(10, Node(11, None))
    print(collect(head, out))
    print(len(out))
    return 0


main()
"""


class CursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.cases = {}
        for name, text in (("param_cursor", PARAM_CURSOR), ("local_cursor", LOCAL_CURSOR),
                           ("reader_call", READER_CALL), ("writer_call", WRITER_CALL),
                           ("cleared", CLEARED), ("field_written", FIELD_WRITTEN),
                           ("appended", APPENDED)):
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

    def test_parameter_cursor_takes_no_reference(self):
        self.check("param_cursor")
        body = body_of(self.cases["param_cursor"][1], "total")
        self.assertEqual(body.count("ail_obj_retain("), 0)
        self.assertNotIn("ail_obj_release(v_n)", body)
        self.assertNotIn("ail_obj_store_Node(&v_n", body)
        self.assertIn("v_n = (ail_nn_Node(v_n))->f_next;", body)

    def test_local_cursor_from_a_borrowed_parameter(self):
        self.check("local_cursor")
        body = body_of(self.cases["local_cursor"][1], "total")
        self.assertNotIn("ail_obj_store_Node(&v_n", body)
        self.assertIn("v_n = v_head;", body)
        self.assertIn("v_n = (ail_nn_Node(v_n))->f_next;", body)

    def test_a_pure_reader_call_keeps_the_cursor(self):
        self.check("reader_call")
        body = body_of(self.cases["reader_call"][1], "total")
        self.assertNotIn("ail_obj_store_Node(&v_n", body)
        self.assertNotIn("ail_obj_retain(v_n)", body)
        self.assertIn("v_n = (ail_nn_Node(v_n))->f_next;", body)

    def test_a_call_that_writes_the_field_refuses_the_cursor(self):
        program = self.check("writer_call")
        self.assertIn("ail_obj_store_Node(&v_n", body_of(program, "total"))

    def test_clearing_the_owner_refuses_the_cursor(self):
        program = self.check("cleared")
        self.assertIn("ail_obj_store_Node(&v_item", body_of(program, "scan"))

    def test_reassigning_the_field_refuses_the_cursor(self):
        program = self.check("field_written")
        self.assertIn("ail_obj_store_Node(&v_n", body_of(program, "total"))

    def test_appending_the_cursor_refuses_it(self):
        program = self.check("appended")
        self.assertIn("ail_obj_store_Node(&v_n", body_of(program, "collect"))

    def test_switch_is_the_escape_hatch(self):
        text = Path(self.directory.name, "param_cursor.py").read_text(encoding="utf-8")
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
        self.assertIn("ail_obj_store_Node(&v_n", body_of(program, "total"))


class AnalysisTests(unittest.TestCase):
    def cursors(self, text):
        tree = ast.parse(text)
        return borrow.analyze_cursors(tree, borrow.analyze(tree, False, {"main"}), False)

    def test_parameter_and_local_cursors(self):
        self.assertEqual(sorted(self.cursors(PARAM_CURSOR).get("total", ())), ["n"])
        self.assertEqual(sorted(self.cursors(LOCAL_CURSOR).get("total", ())), ["n"])

    def test_refused_cases(self):
        self.assertNotIn("item", self.cursors(CLEARED).get("scan", ()))
        self.assertNotIn("n", self.cursors(FIELD_WRITTEN).get("total", ()))
        self.assertNotIn("n", self.cursors(APPENDED).get("collect", ()))
        self.assertNotIn("n", self.cursors(WRITER_CALL).get("total", ()))

    def test_a_pure_reader_call_is_a_cursor(self):
        self.assertIn("n", self.cursors(READER_CALL).get("total", ()))

    def test_a_store_before_the_binding_does_not_refuse(self):
        text = NODE + """
def total(head: Node | None, other: Node) -> int:
    other.next = None
    n = head
    acc = 0
    while n is not None:
        acc += n.value
        n = n.next
    return acc


def main() -> int:
    return 0


main()
"""
        self.assertIn("n", self.cursors(text).get("total", ()))

    def test_stored_into_a_list_literal_is_refused(self):
        text = NODE + """
def pack(head: Node | None, out: list[Node]) -> int:
    n = head
    ys = [n]
    return len(ys)


def main() -> int:
    return 0


main()
"""
        self.assertNotIn("n", self.cursors(text).get("pack", ()))

    def test_returned_from_the_walk_is_refused(self):
        text = NODE + """
def last(n: Node | None) -> Node | None:
    while n is not None:
        if n.next is None:
            return n
        n = n.next
    return None


def main() -> int:
    return 0


main()
"""
        self.assertNotIn("n", self.cursors(text).get("last", ()))


if __name__ == "__main__":
    unittest.main()
