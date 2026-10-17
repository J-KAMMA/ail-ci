import sys


class TrieNode:
    __slots__ = ("children", "is_word")

    def __init__(self) -> None:
        self.children: dict[str, "TrieNode"] = {}
        self.is_word: bool = False


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1:1 + n]

    root = TrieNode()
    node_count = 1  # the root itself
    for word in words:
        node = root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
                node_count += 1
            node = node.children[ch]
        node.is_word = True

    out = [str(node_count)]
    if words:
        prefix = words[0][:2]
        out.extend(sorted(w for w in words if w.startswith(prefix)))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
