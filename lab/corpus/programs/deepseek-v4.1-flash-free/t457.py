import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(x) for x in data[1:1 + n]]

    out = []
    for x in numbers:
        line = " ".join([
            f"{x:10d}",
            f"{x:*>10d}",
            f"{x:+d}",
            f"{x:x}",
            f"{x:b}",
            f"{x / 100:.2%}",
            f"{x:.2e}",
            f"{x:,}",
        ])
        out.append(line)
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
