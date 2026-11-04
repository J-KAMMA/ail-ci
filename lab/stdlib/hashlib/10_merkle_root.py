import hashlib


def merkle_root(leaves: list[bytes]) -> bytes:
    level = leaves
    while len(level) > 1:
        next_level: list[bytes] = []
        i = 0
        while i + 1 < len(level):
            next_level.append(hashlib.sha256(level[i] + level[i + 1]).digest())
            i += 2
        if i < len(level):
            next_level.append(hashlib.sha256(level[i] + level[i]).digest())
        level = next_level
    return level[0]


def main() -> None:
    leaves: list[bytes] = []
    for i in range(1000):
        leaves.append(hashlib.sha256(b"leaf-" + str(i).encode()).digest())
    root = merkle_root(leaves)
    print(len(root), root.hex())
    changed = leaves[:]
    changed[500] = hashlib.sha256(b"replacement").digest()
    print(merkle_root(changed).hex() != root.hex())


main()
