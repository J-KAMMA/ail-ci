import sys


def main() -> None:
    data = sys.stdin.read().split()
    seed = int(data[0])
    n = int(data[1])

    a: int = 1103515245
    modulus: int = 2**31

    x: int = seed
    out: list[str] = []
    for _ in range(n):
        x = (a * x + 11) % modulus
        out.append(str(x % 100))

    if out:
        sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
