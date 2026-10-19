import heapq
import sys


def main() -> None:
    heap: list[int] = []
    out: list[str] = []

    for raw in sys.stdin:
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0].lower()

        if cmd == "push" and len(parts) >= 2:
            heapq.heappush(heap, int(parts[1]))
        elif cmd == "pop":
            if heap:
                out.append(str(heapq.heappop(heap)))
            else:
                out.append("EMPTY")
        elif cmd == "peek":
            if heap:
                out.append(str(heap[0]))
            else:
                out.append("EMPTY")
        elif cmd == "size":
            out.append(str(len(heap)))

    if out:
        sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
