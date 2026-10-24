# task: Implement a generator that performs an in-order traversal of a binary tree stored as nested tuples and print the visited values.
from typing import Optional, Tuple, Union, Iterator

# A binary tree stored as nested tuples:
#   None                      -> empty tree
#   (left, value, right)      -> node with value and two subtrees
Tree = Optional[Tuple[Union["Tree", None], object, Union["Tree", None]]]


def inorder(tree: Tree) -> Iterator[object]:
    """Generate values of the tree in in-order (left, node, right) sequence."""
    if tree is None:
        return
    left, value, right = tree
    yield from inorder(left)
    yield value
    yield from inorder(right)


def build_sample_tree() -> Tree:
    """Construct a fixed sample binary search tree as nested tuples."""
    leaf_1 = (None, 1, None)
    leaf_4 = (None, 4, None)
    leaf_6 = (None, 6, None)
    leaf_9 = (None, 9, None)
    left_branch = (leaf_1, 3, leaf_4)
    right_branch = (leaf_6, 8, leaf_9)
    return (left_branch, 5, right_branch)


def main() -> None:
    tree = build_sample_tree()
    values = list(inorder(tree))
    print("In-order traversal:")
    for value in inorder(tree):
        print(value)
    print("As list:", values)


if __name__ == "__main__":
    main()
