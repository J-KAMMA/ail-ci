import sys


class TrieNode:
    def __init__(self) -> None:
        self.children: dict[str, "TrieNode"] = {}
        self.is_end: bool = False


class Trie:
    def __init__(self) -> None:
        self.root: TrieNode = TrieNode()
        self.node_count: int = 1  # the root counts as a node

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            child = node.children.get(ch)
            if child is None:
                child = TrieNode()
                node.children[ch] = child
                self.node_count += 1
            node = child
        node.is_end = True

    def find(self, prefix: str) -> TrieNode | None:
        node = self.root
        for ch in prefix:
            child = node.children.get(ch)
            if child is None:
                return None
            node = child
        return node

    def words_with_prefix(self, prefix: str) -> list[str]:
        start = self.find(prefix)
        if start is None:
            return []
        results: list[str] = []
        stack: list[tuple[TrieNode, str]] = [(start, prefix)]
        while stack:
            node, current = stack.pop()
            if node.is_end:
                results.append(current)
            for ch, child in node.children.items():
                stack.append((child, current + ch))
        results.sort()
        return results


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1:1 + n]

    trie = Trie()
    for word in words:
        trie.insert(word)

    print(trie.node_count)

    if words:
        prefix = words[0][:2]
        for word in trie.words_with_prefix(prefix):
            print(word)


if __name__ == "__main__":
    main()
