"""Tree building and traversal over integer node records."""


class Node:
    def __init__(self, key: int, value: int) -> None:
        self.key = key
        self.value = value
        self.left = -1
        self.right = -1


class Tree:
    def __init__(self) -> None:
        self.keys = []
        self.left = []
        self.right = []
        self.size = 0

    def insert(self, key: int) -> None:
        self.keys.append(key)
        self.left.append(-1)
        self.right.append(-1)
        idx = self.size
        self.size += 1
        if idx == 0:
            return
        cur = 0
        while True:
            if key < self.keys[cur]:
                nxt = self.left[cur]
                if nxt < 0:
                    self.left[cur] = idx
                    return
                cur = nxt
            else:
                nxt = self.right[cur]
                if nxt < 0:
                    self.right[cur] = idx
                    return
                cur = nxt

    def height(self) -> int:
        return self._height(0)

    def _height(self, idx: int) -> int:
        if idx < 0:
            return 0
        a = self._height(self.left[idx])
        b = self._height(self.right[idx])
        if a > b:
            return a + 1
        return b + 1

    def inorder_sum(self) -> int:
        return self._inorder(0)

    def _inorder(self, idx: int) -> int:
        if idx < 0:
            return 0
        return self._inorder(self.left[idx]) + self.keys[idx] + self._inorder(self.right[idx])

    def min_key(self) -> int:
        cur = 0
        while self.left[cur] >= 0:
            cur = self.left[cur]
        return self.keys[cur]

    def max_key(self) -> int:
        cur = 0
        while self.right[cur] >= 0:
            cur = self.right[cur]
        return self.keys[cur]

    def depth_sum(self) -> int:
        return self._depth(0, 0)

    def _depth(self, idx: int, d: int) -> int:
        if idx < 0:
            return 0
        return d + self._depth(self.left[idx], d + 1) + self._depth(self.right[idx], d + 1)


def build_tree(keys: list[int]) -> Tree:
    t = Tree()
    for k in keys:
        t.insert(k)
    return t


def count_nodes(t: Tree) -> int:
    return t.size
