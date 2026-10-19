import heapq
import sys


class TaskQueue:
    """A binary-heap-based priority queue of (priority, name) tuples."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, str]] = []

    def push(self, priority: int, name: str) -> None:
        heapq.heappush(self._heap, (priority, name))

    def pop(self) -> tuple[int, str]:
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        return len(self._heap)

    def pop_all(self) -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []
        while self._heap:
            result.append(self.pop())
        return result


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    words = data[1 : 1 + n]

    queue = TaskQueue()
    for word in words:
        queue.push(len(word), word)

    for priority, name in queue.pop_all():
        print(priority, name)


if __name__ == "__main__":
    main()
