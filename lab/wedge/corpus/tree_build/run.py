"""Driver for tree_build: insert keys and traverse the tree."""
import tree_build as m

N = 60000
ROUNDS = 80


def main() -> None:
    keys = []
    for i in range(N):
        keys.append((i * 2654435761) % 1000003)
    t = m.build_tree(keys)
    total = 0
    for _r in range(ROUNDS):
        total += t.height() + t.inorder_sum() + t.depth_sum()
        total += t.min_key() + t.max_key()
    print("nodes", m.count_nodes(t))
    print("height", t.height())
    print("sum", t.inorder_sum())
    print("depth", t.depth_sum())
    print("min", t.min_key())
    print("max", t.max_key())
    print("total", total)


main()
