"""`xs[i].field` for a numeric field reads the element without retaining it.

That is only done when the list and the index are plain names or an int literal; the reads here
cover negative and out-of-range indexes, an element whose only owner is the list, and a list
replaced right after the read.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''struct Node { parent: int; weight: float; name: str; }
fn scan(nodes: list[Node], start: int) -> int {
    let i: int = start + 1;
    while i < len(nodes) and nodes[i].parent >= start { i += 1; }
    return i;
}
fn main() -> int {
    let nodes: list[Node] = [];
    for k in range(6) { nodes.append(Node(k // 2, 0.5 * k, "n" + str(k))); }
    let last: int = -1;
    print(scan(nodes, 0), scan(nodes, 2), nodes[last].parent, nodes[0].weight, nodes[5].weight);
    let total: float = 0.0;
    for k in range(len(nodes)) { total += nodes[k].weight; }
    print(total);
    let p: int = nodes[1].parent;
    nodes = [];
    print(p, len(nodes));
    let other: list[Node] = [Node(7, 1.5, "x")];
    let big: int = 3;
    try { print(other[big].parent); } except IndexError { print("IndexError"); }
    return 0;
}'''


class BorrowedElementFieldTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_numeric_element_fields(self):
        program = build(self, 'borrowed_element_fields', SOURCE)
        result = subprocess.run([str(program)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.decode()),
                         (0, '6 3 2 0.0 2.5\n7.5\n0 0\nIndexError\n'), result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
