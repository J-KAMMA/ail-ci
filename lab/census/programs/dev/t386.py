import sys


def main() -> None:
    tuples: list[tuple[int, int]] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 2)
        if len(parts) < 2:
            continue
        a = int(parts[0].strip())
        b = int(parts[1].strip())
        tuples.append((a, b))

    tuples.sort(key=lambda t: (t[1], -t[0]))

    for a, b in tuples:
        print(f"{a} {b}")


if __name__ == "__main__":
    main()
