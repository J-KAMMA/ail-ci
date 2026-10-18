import sys
import heapq


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    intervals: list[tuple[int, int]] = []
    idx = 1
    for _ in range(n):
        start = int(data[idx])
        end = int(data[idx + 1])
        idx += 2
        intervals.append((start, end))

    if n == 0:
        print(0, 0)
        return

    ordered = sorted(intervals)

    # Minimum number of rooms via a min-heap of end times.
    heap: list[int] = []
    rooms = 0
    for start, end in ordered:
        while heap and heap[0] <= start:
            heapq.heappop(heap)
        heapq.heappush(heap, end)
        if len(heap) > rooms:
            rooms = len(heap)

    # Total idle time between merged intervals.
    idle = 0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start > cur_end:
            idle += start - cur_end
            cur_start, cur_end = start, end
        elif end > cur_end:
            cur_end = end

    print(rooms, idle)


if __name__ == "__main__":
    main()
