"""Driver for ast_lint: build a nested-tuple tree and walk it."""
import ast_lint as m

DEPTH = 7
WIDTH = 4
ROUNDS = 35


def build(depth: int, width: int, seed: int) -> tuple:
    if depth == 0:
        return ("leaf", seed % 7, "name_x", seed)
    parts = []
    i = 0
    while i < width:
        parts.append(build(depth - 1, width, seed * 3 + i))
        i += 1
    return ("node", seed, tuple(parts))


def main() -> None:
    tree = build(DEPTH, WIDTH, 1)
    total_nodes = 0
    total_depth = 0
    total_tags = 0
    total_ints = 0
    total_sum = 0
    total_leaves = 0
    found = 0
    for r in range(ROUNDS):
        total_nodes += m.node_count(tree)
        d = m.max_depth(tree)
        if d > total_depth:
            total_depth = d
        total_tags += m.count_tag(tree, "name_x")
        total_ints += m.count_ints(tree)
        total_sum += m.sum_ints(tree)
        total_leaves += m.leaves(tree)
        if m.has_tag(tree, "leaf") and (r % 2 == 0):
            found += 1
    print("nodes", total_nodes)
    print("depth", total_depth)
    print("tags", total_tags)
    print("ints", total_ints)
    print("sum", total_sum)
    print("leaves", total_leaves)
    print("found", found)


main()
