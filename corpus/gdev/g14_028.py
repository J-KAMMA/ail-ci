# task: Create a dataclass tree node Node with children list and compute the depth of a constructed tree.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """A tree node holding a value and a list of child nodes."""
    value: str
    children: list[Node] = field(default_factory=list)

    def add_child(self, child: Node) -> Node:
        """Append a child node and return it for convenient chaining."""
        self.children.append(child)
        return child


def depth(node: Node) -> int:
    """Return the depth of the tree rooted at node.

    A single node has depth 1; an empty tree (no node) would be 0,
    but since we always have a root here, the minimum depth is 1.
    """
    if not node.children:
        return 1
    return 1 + max(depth(child) for child in node.children)


def build_sample_tree() -> Node:
    """Construct a fixed, deterministic tree for demonstration."""
    root = Node("root")

    a = root.add_child(Node("a"))
    b = root.add_child(Node("b"))
    c = root.add_child(Node("c"))

    a1 = a.add_child(Node("a1"))
    a1.add_child(Node("a1x"))
    a1.add_child(Node("a1y"))

    b.add_child(Node("b1"))

    c1 = c.add_child(Node("c1"))
    c1.add_child(Node("c1x"))
    c1.add_child(Node("c1y")).add_child(Node("c1yz"))

    return root


def main() -> None:
    root = build_sample_tree()
    print(f"Root value: {root.value}")
    print(f"Direct children: {len(root.children)}")
    print(f"Depth of tree: {depth(root)}")

    for child in root.children:
        print(f"Depth of subtree '{child.value}': {depth(child)}")


if __name__ == "__main__":
    main()
