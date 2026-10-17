import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    total_original = 0.0
    total_rounded = 0
    idx = 1
    for _ in range(n):
        _name = data[idx]
        value = float(data[idx + 1])
        idx += 2
        total_original += value
        total_rounded += round(value)
    print(total_rounded)
    print(f"{total_original:.2f}")


if __name__ == "__main__":
    main()
