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

LIST_AIL = 'import sys\n\nclass ListNode:\n\n    def __init__(self, val: int, next: ListNode | None):\n        self.val = val\n        self.next = next\n\n    def total(self) -> int:\n        if self.next is None:\n            return self.val\n        return self.val + self.next.total()\n\nclass Stack:\n\n    def __init__(self, head: ListNode | None, size: int):\n        self.head = head\n        self.size = size\n\ndef push(s: Stack, v: int) -> None:\n    s.head = ListNode(v, s.head)\n    s.size += 1\n\ndef pop(s: Stack) -> int:\n    h = s.head\n    if h is None:\n        raise IndexError(\'empty\')\n    s.head = h.next\n    s.size -= 1\n    return h.val\n\ndef find(head: ListNode | None, v: int) -> ListNode | None:\n    cur = head\n    while cur is not None:\n        if cur.val == v:\n            return cur\n        cur = cur.next\n    return None\n\ndef length(head: ListNode | None) -> int:\n    n = 0\n    cur = head\n    while cur:\n        n += 1\n        cur = cur.next\n    return n\n\ndef reverse(head: ListNode | None) -> ListNode | None:\n    prev: ListNode | None = None\n    cur = head\n    while cur != None:\n        nxt = cur.next\n        cur.next = prev\n        prev = cur\n        cur = nxt\n    return prev\n\ndef main() -> int:\n    s = Stack(None, 0)\n    for i in range(5):\n        push(s, i * 10)\n    print(s.size, length(s.head), s.head.total())\n    f = find(s.head, 20)\n    if f is not None:\n        print(\'found\', f.val)\n    if find(s.head, 99) is None:\n        print(\'missing\')\n    s.head = reverse(s.head)\n    cur = s.head\n    while cur is not None:\n        print(cur.val)\n        cur = cur.next\n    print(pop(s), pop(s), s.size)\n    a = ListNode(1, None)\n    b = ListNode(2, a)\n    print(b.next is a, a is b, b.next is not None)\n    try:\n        z = find(s.head, 12345)\n        print(z.val)\n    except RuntimeError as e:\n        print(\'caught\', e.kind, e.message)\n    try:\n        z = find(s.head, 12345)\n        print(z.total())\n    except RuntimeError as e:\n        print(\'caught method\', e.message)\n    while s.size > 0:\n        pop(s)\n    try:\n        pop(s)\n    except IndexError:\n        print(\'empty\')\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

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

TREE_AIL = 'import sys\n\nclass Out:\n\n    def __init__(self, xs: list[int]):\n        self.xs = xs\n\nclass Tree:\n\n    def __init__(self, key: int, count: int, left: Tree | None, right: Tree | None):\n        self.key = key\n        self.count = count\n        self.left = left\n        self.right = right\n\n    def size(self) -> int:\n        n = 1\n        if self.left is not None:\n            n += self.left.size()\n        if self.right is not None:\n            n += self.right.size()\n        return n\n\ndef insert(t: Tree | None, k: int) -> Tree:\n    if t is None:\n        return Tree(k, 1, None, None)\n    if k < t.key:\n        t.left = insert(t.left, k)\n    elif k > t.key:\n        t.right = insert(t.right, k)\n    else:\n        t.count += 1\n    return t\n\ndef height(t: Tree | None) -> int:\n    if not t:\n        return 0\n    return 1 + max(height(t.left), height(t.right))\n\ndef inorder(t: Tree | None, out: Out) -> None:\n    if t == None:\n        return\n    inorder(t.left, out)\n    out.xs.append(t.key)\n    inorder(t.right, out)\n\ndef lookup(t: Tree | None, k: int) -> int:\n    cur = t\n    while cur != None:\n        if k == cur.key:\n            return cur.count\n        if k < cur.key:\n            cur = cur.left\n        else:\n            cur = cur.right\n    return 0\n\ndef main() -> int:\n    root: Tree | None = None\n    x = 12345\n    for i in range(2000):\n        x = (x * 1103515245 + 12345) % 2147483648\n        root = insert(root, x % 500)\n    print(height(root), lookup(root, 7), lookup(root, 1000))\n    o = Out([])\n    inorder(root, o)\n    print(len(o.xs), o.xs[0], o.xs[len(o.xs) - 1], root.size())\n    root.left = None\n    print(root.size())\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

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

DEEP_AIL = 'import sys\n\nclass Cell:\n\n    def __init__(self, v: int, next: Cell | None):\n        self.v = v\n        self.next = next\n\ndef build(n: int) -> Cell | None:\n    head: Cell | None = None\n    for i in range(n):\n        head = Cell(i, head)\n    return head\n\ndef total(h: Cell | None) -> int:\n    s = 0\n    c = h\n    while c is not None:\n        s += c.v\n        c = c.next\n    return s\n\ndef main() -> int:\n    h = build(1500000)\n    print(total(h))\n    h = None\n    print(total(build(10)))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

DEEP_PY = """
print(sum(range(1500000)))
print(sum(range(10)))
"""

NESTED_AIL = 'import sys\n\nclass Node:\n\n    def __init__(self, children: list[Node], v: int):\n        self.children = children\n        self.v = v\n\nclass A:\n\n    def __init__(self, b: B | None, v: int):\n        self.b = b\n        self.v = v\n\nclass B:\n\n    def __init__(self, a: A | None, w: int):\n        self.a = a\n        self.w = w\n\ndef total(n: Node) -> int:\n    s = n.v\n    for c in n.children:\n        s += total(c)\n    return s\n\ndef main() -> int:\n    r = Node([], 1)\n    r.children.append(Node([], 2))\n    r.children.append(Node([Node([], 4)], 3))\n    print(total(r))\n    a = A(None, 1)\n    b = B(a, 2)\n    a.b = b\n    print(a.b.w, b.a.v)\n    a.b = None\n    print(a.b is None)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

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
        ran = _build_and_run('import sys\n\nclass N:\n\n    def __init__(self, v: int, nx: N | None):\n        self.v = v\n        self.nx = nx\n\ndef main() -> int:\n    a = N(1, None)\n    print(a.v)\n    print(a.nx.v)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', "uncaught")
        self.assertEqual(ran.returncode, 1)
        self.assertEqual(ran.stdout, "1\n")
        self.assertIn("RuntimeError: field access on None", ran.stderr)

    def test_refusals_name_the_fix(self):
        for source, text in [
            ('import sys\n\nclass N:\n\n    def __init__(self, v: int):\n        self.v = v\n\ndef main() -> int:\n    x: int | None = 3\n    print(x)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', "only a struct type can be None"),
            ('import sys\n\nclass N:\n\n    def __init__(self, v: int, nx: N | None):\n        self.v = v\n        self.nx = nx\n\ndef main() -> int:\n    a = N(1, None)\n    a.v = None\n    print(a.v)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
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
