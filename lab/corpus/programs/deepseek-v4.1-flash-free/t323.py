import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    intervals = []
    idx = 1
    for _ in range(n):
        s = int(data[idx])
        e = int(data[idx + 1])
        idx += 2
        intervals.append((s, e))

    intervals.sort(key=lambda x: (x[1], x[0]))

    chosen = []
    last_end = None
    for s, e in intervals:
        if last_end is None or s >= last_end:
            chosen.append((s, e))
            last_end = e

    out = [str(len(chosen))]
    for s, e in chosen:
        out.append(f"{s} {e}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
