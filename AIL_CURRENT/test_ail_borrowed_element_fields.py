"""`xs[i].field` for a numeric field reads the element without retaining it.

That is only done when the list and the index are plain names or an int literal; the reads here
cover negative and out-of-range indexes, an element whose only owner is the list, and a list
replaced right after the read.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = 'import sys\n\nclass Node:\n\n    def __init__(self, parent: int, weight: float, name: str):\n        self.parent = parent\n        self.weight = weight\n        self.name = name\n\ndef scan(nodes: list[Node], start: int) -> int:\n    i: int = start + 1\n    while i < len(nodes) and nodes[i].parent >= start:\n        i += 1\n    return i\n\ndef main() -> int:\n    nodes: list[Node] = []\n    for k in range(6):\n        nodes.append(Node(k // 2, 0.5 * k, \'n\' + str(k)))\n    last: int = -1\n    print(scan(nodes, 0), scan(nodes, 2), nodes[last].parent, nodes[0].weight, nodes[5].weight)\n    total: float = 0.0\n    for k in range(len(nodes)):\n        total += nodes[k].weight\n    print(total)\n    p: int = nodes[1].parent\n    nodes = []\n    print(p, len(nodes))\n    other: list[Node] = [Node(7, 1.5, \'x\')]\n    big: int = 3\n    try:\n        print(other[big].parent)\n    except IndexError:\n        print(\'IndexError\')\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


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
