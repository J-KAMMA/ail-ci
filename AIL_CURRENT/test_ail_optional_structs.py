"""`Node | None` struct fields, parameters, results and locals: linked lists, trees, None errors.

Each AIL program is compared with the same program run by CPython (None access there raises
AttributeError, here RuntimeError "field access on None"; the Python twins catch it and print the
AIL spelling).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LIST_AIL = """
struct ListNode { val: int; next: ListNode | None; }
struct Stack { head: Optional[ListNode]; size: int; }

fn push(s: Stack, v: int) -> void {
    s.head = ListNode(v, s.head);
    s.size += 1;
}
fn pop(s: Stack) -> int {
    let h = s.head;
    if h is None { raise IndexError("empty"); }
    s.head = h.next;
    s.size -= 1;
    return h.val;
}
fn find(head: ListNode | None, v: int) -> ListNode | None {
    let cur = head;
    while cur is not None {
        if cur.val == v { return cur; }
        cur = cur.next;
    }
    return None;
}
fn length(head: ListNode | None) -> int {
    let n = 0;
    let cur = head;
    while cur { n += 1; cur = cur.next; }
    return n;
}
fn reverse(head: ListNode | None) -> ListNode | None {
    let prev: ListNode | None = None;
    let cur = head;
    while cur != None {
        let nxt = cur.next;
        cur.next = prev;
        prev = cur;
        cur = nxt;
    }
    return prev;
}
impl ListNode {
    fn total(self) -> int {
        if self.next is None { return self.val; }
        return self.val + self.next.total();
    }
}
fn main() {
    let s = Stack(None, 0);
    for i in range(5) { push(s, i * 10); }
    print(s.size, length(s.head), s.head.total());
    let f = find(s.head, 20);
    if f is not None { print("found", f.val); }
    if find(s.head, 99) is None { print("missing"); }
    s.head = reverse(s.head);
    let cur = s.head;
    while cur is not None { print(cur.val); cur = cur.next; }
    print(pop(s), pop(s), s.size);
    let a = ListNode(1, None);
    let b = ListNode(2, a);
    print(b.next is a, a is b, b.next is not None);
    try {
        let z = find(s.head, 12345);
        print(z.val);
    } except RuntimeError as e {
        print("caught", e.kind, e.message);
    }
    try {
        let z = find(s.head, 12345);
        print(z.total());
    } except RuntimeError as e {
        print("caught method", e.message);
    }
    while s.size > 0 { pop(s); }
    try { pop(s); } except IndexError { print("empty"); }
}
"""

LIST_PY = """
class ListNode:
    def __init__(self, val, next): self.val = val; self.next = next
    def total(self):
        if self.next is None: return self.val
        return self.val + self.next.total()
class Stack:
    def __init__(self, head, size): self.head = head; self.size = size
def push(s, v):
    s.head = ListNode(v, s.head); s.size += 1
def pop(s):
    h = s.head
    if h is None: raise IndexError("empty")
    s.head = h.next; s.size -= 1
    return h.val
def find(head, v):
    cur = head
    while cur is not None:
        if cur.val == v: return cur
        cur = cur.next
    return None
def length(head):
    n = 0; cur = head
    while cur: n += 1; cur = cur.next
    return n
def reverse(head):
    prev = None; cur = head
    while cur != None:
        nxt = cur.next; cur.next = prev; prev = cur; cur = nxt
    return prev
s = Stack(None, 0)
for i in range(5): push(s, i * 10)
print(s.size, length(s.head), s.head.total())
f = find(s.head, 20)
if f is not None: print("found", f.val)
if find(s.head, 99) is None: print("missing")
s.head = reverse(s.head)
cur = s.head
while cur is not None:
    print(cur.val); cur = cur.next
print(pop(s), pop(s), s.size)
a = ListNode(1, None); b = ListNode(2, a)
print(b.next is a, a is b, b.next is not None)
try:
    z = find(s.head, 12345); print(z.val)
except AttributeError:
    print("caught", "RuntimeError", "field access on None")
try:
    z = find(s.head, 12345); print(z.total())
except AttributeError:
    print("caught method", "field access on None")
while s.size > 0: pop(s)
try: pop(s)
except IndexError: print("empty")
"""

TREE_AIL = """
struct Out { xs: list[int]; }
struct Tree { key: int; count: int; left: Tree | None; right: Tree | None; }

impl Tree {
    fn size(self) -> int {
        let n = 1;
        if self.left is not None { n += self.left.size(); }
        if self.right is not None { n += self.right.size(); }
        return n;
    }
}
fn insert(t: Tree | None, k: int) -> Tree {
    if t is None { return Tree(k, 1, None, None); }
    if k < t.key { t.left = insert(t.left, k); }
    elif k > t.key { t.right = insert(t.right, k); }
    else { t.count += 1; }
    return t;
}
fn height(t: Tree | None) -> int {
    if not t { return 0; }
    return 1 + max(height(t.left), height(t.right));
}
fn inorder(t: Tree | None, out: Out) -> void {
    if t == None { return; }
    inorder(t.left, out);
    out.xs.append(t.key);
    inorder(t.right, out);
}
fn lookup(t: Tree | None, k: int) -> int {
    let cur = t;
    while cur != None {
        if k == cur.key { return cur.count; }
        if k < cur.key { cur = cur.left; } else { cur = cur.right; }
    }
    return 0;
}
fn main() {
    let root: Tree | None = None;
    let x = 12345;
    for i in range(2000) {
        x = (x * 1103515245 + 12345) % 2147483648;
        root = insert(root, x % 500);
    }
    print(height(root), lookup(root, 7), lookup(root, 1000));
    let o = Out([]);
    inorder(root, o);
    print(len(o.xs), o.xs[0], o.xs[len(o.xs) - 1], root.size());
    root.left = None;
    print(root.size());
}
"""

TREE_PY = """
class Tree:
    def __init__(self, key, count, left, right):
        self.key = key; self.count = count; self.left = left; self.right = right
    def size(self):
        n = 1
        if self.left is not None: n += self.left.size()
        if self.right is not None: n += self.right.size()
        return n
def insert(t, k):
    if t is None: return Tree(k, 1, None, None)
    if k < t.key: t.left = insert(t.left, k)
    elif k > t.key: t.right = insert(t.right, k)
    else: t.count += 1
    return t
def height(t):
    if not t: return 0
    return 1 + max(height(t.left), height(t.right))
def inorder(t, out):
    if t == None: return
    inorder(t.left, out); out.append(t.key); inorder(t.right, out)
def lookup(t, k):
    cur = t
    while cur != None:
        if k == cur.key: return cur.count
        cur = cur.left if k < cur.key else cur.right
    return 0
root = None; x = 12345
for i in range(2000):
    x = (x * 1103515245 + 12345) % 2147483648
    root = insert(root, x % 500)
print(height(root), lookup(root, 7), lookup(root, 1000))
o = []; inorder(root, o)
print(len(o), o[0], o[-1], root.size())
root.left = None
print(root.size())
"""

DEEP_AIL = """
struct Cell { v: int; next: Cell | None; }
fn build(n: int) -> Cell | None {
    let head: Cell | None = None;
    for i in range(n) { head = Cell(i, head); }
    return head;
}
fn total(h: Cell | None) -> int {
    let s = 0;
    let c = h;
    while c is not None { s += c.v; c = c.next; }
    return s;
}
fn main() {
    let h = build(1500000);
    print(total(h));
    h = None;
    print(total(build(10)));
}
"""

DEEP_PY = """
print(sum(range(1500000)))
print(sum(range(10)))
"""

NESTED_AIL = """
struct Node { children: list[Node]; v: int; }
struct A { b: B | None; v: int; }
struct B { a: A | None; w: int; }
fn total(n: Node) -> int { let s = n.v; for c in n.children { s += total(c); } return s; }
fn main() {
    let r = Node([], 1);
    r.children.append(Node([], 2));
    r.children.append(Node([Node([], 4)], 3));
    print(total(r));
    let a = A(None, 1);
    let b = B(a, 2);
    a.b = b;
    print(a.b.w, b.a.v);
    a.b = None;
    print(a.b is None);
}
"""

NESTED_PY = """
def total(n): return n[1] + sum(total(c) for c in n[0])
print(total(([(([], 2)), (([(([], 4))], 3))], 1)))
print(2, 1)
print(True)
"""


def _build_and_run(source, name):
    with tempfile.TemporaryDirectory() as directory:
        src, exe = Path(directory, name + ".ail"), Path(directory, name)
        src.write_text(source)
        built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(src), "-o", str(exe)],
                               capture_output=True, text=True, timeout=600)
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)


def _python(code):
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60).stdout


MIXED_PY = """
class Node:
    def __init__(self, a: int):
        self.a = a


def find(k: int) -> Node | None:
    if k > 0:
        return Node(k)
    return None


def name(k: int) -> str | None:
    if k > 0:
        return "x"
    return None


def main():
    row = find(1)
    if row is not None:
        print(row.a)
    s = name(1)
    print(s)
    r2 = find(0)
    print(r2 is None, r2 is not None, name(0) is None)
    t: Node | None = find(2)
    print(t is None)


main()
"""


class OptionalStructTests(unittest.TestCase):
    def check(self, source, python, name):
        ran = _build_and_run(source, name)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, _python(python))

    def test_linked_list_stack(self):
        self.check(LIST_AIL, LIST_PY, "list")

    def test_binary_search_tree(self):
        self.check(TREE_AIL, TREE_PY, "tree")

    def test_million_node_list_frees_without_deep_recursion(self):
        self.check(DEEP_AIL, DEEP_PY, "deep")

    def test_list_children_and_mutual_recursion(self):
        self.check(NESTED_AIL, NESTED_PY, "nested")

    def test_a_class_optional_and_a_scalar_optional_in_one_program(self):
        # `node is None` where node is a class instance was read as a comparison of a scalar Optional (G11)
        with tempfile.TemporaryDirectory() as directory:
            src, exe = Path(directory, "mixed.py"), Path(directory, "mixed")
            src.write_text(MIXED_PY)
            env = dict(os.environ, AIL_NO_GENERAL="1")
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=600, env=env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, _python(MIXED_PY))

    def test_uncaught_none_access_exits_one(self):
        ran = _build_and_run("""
struct N { v: int; nx: N | None; }
fn main() { let a = N(1, None); print(a.v); print(a.nx.v); }
""", "uncaught")
        self.assertEqual(ran.returncode, 1)
        self.assertEqual(ran.stdout, "1\n")
        self.assertIn("RuntimeError: field access on None", ran.stderr)

    def test_refusals_name_the_fix(self):
        for source, text in [
            ("struct N { v: int; }\nfn main() { let x: int | None = 3; print(x); }", "only a struct type can be None"),
            ("struct N { v: int; nx: N | None; }\nfn main() { let a = N(1, None); a.v = None; print(a.v); }",
             "numeric field"),
        ]:
            with tempfile.TemporaryDirectory() as directory:
                src = Path(directory, "m.ail")
                src.write_text(source)
                built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(src),
                                        "-o", str(Path(directory, "m"))], capture_output=True, text=True, timeout=300)
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(text, built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
