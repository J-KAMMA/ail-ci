# task: Write a script that solves a hardcoded word-ladder puzzle by BFS over a small fixed dictionary and prints the shortest transformation sequence.
from collections import deque
from string import ascii_lowercase

VOCABULARY: frozenset[str] = frozenset(
    {
        "cold", "cord", "card", "ward", "warm", "word", "worm",
        "wold", "bold", "bolt", "colt", "cart", "part", "port",
        "wart", "wald", "worn", "corn", "cora", "bard", "bare",
        "care", "core", "bore", "more", "mare", "ware", "wire",
        "fire", "fare", "farm", "harm", "hard", "herd", "here",
    }
)


def neighbors(word: str, vocabulary: frozenset[str]) -> list[str]:
    """Return dictionary words differing from `word` by exactly one letter.

    Candidates are generated in a fixed order (position first, then
    alphabetical letter), so the result is deterministic.
    """
    result: list[str] = []
    for i in range(len(word)):
        for letter in ascii_lowercase:
            if letter == word[i]:
                continue
            candidate = word[:i] + letter + word[i + 1:]
            if candidate in vocabulary:
                result.append(candidate)
    return result


def find_ladder(
    start: str, goal: str, vocabulary: frozenset[str]
) -> list[str] | None:
    """Find a shortest transformation sequence using breadth-first search."""
    if start == goal:
        return [start]

    parent: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])

    while queue:
        current = queue.popleft()
        for nxt in neighbors(current, vocabulary):
            if nxt in parent:
                continue
            parent[nxt] = current
            if nxt == goal:
                return _reconstruct(parent, goal)
            queue.append(nxt)

    return None


def _reconstruct(parent: dict[str, str | None], goal: str) -> list[str]:
    """Walk parent links back from `goal` to build the path in order."""
    path: list[str] = []
    node: str | None = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def main() -> None:
    start = "cold"
    goal = "warm"

    print(f"Word ladder: {start.upper()} -> {goal.upper()}")
    print(f"Dictionary size: {len(VOCABULARY)} words")

    ladder = find_ladder(start, goal, VOCABULARY)
    if ladder is None:
        print("No transformation sequence exists.")
        return

    print(f"Shortest sequence ({len(ladder) - 1} steps):")
    for step, word in enumerate(ladder):
        print(f"  {step}: {word.upper()}")


if __name__ == "__main__":
    main()
