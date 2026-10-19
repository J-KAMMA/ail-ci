import heapq
import sys
from typing import List, Tuple


def main() -> None:
    data: List[str] = sys.stdin.read().split()
    if not data:
        return

    n: int = int(data[0])
    words: List[str] = data[1:1 + n]

    heap: List[Tuple[int, int, str]] = []
    for counter, word in enumerate(words):
        heapq.heappush(heap, (len(word), counter, word))

    result: List[str] = []
    while heap:
        _, _, item = heapq.heappop(heap)
        result.append(item)

    for item in result:
        print(item)


if __name__ == "__main__":
    main()
