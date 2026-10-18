import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    a = [int(x) for x in data]
    n = len(a)

    if n <= 1:
        print(0)
        return

    jumps = 0
    current_end = 0
    farthest = 0

    for i in range(n - 1):
        reach = i + abs(a[i])
        if reach > farthest:
            farthest = reach
        if i == current_end:
            if farthest <= i:
                print(-1)
                return
            jumps += 1
            current_end = farthest
            if current_end >= n - 1:
                break

    print(jumps)


if __name__ == "__main__":
    main()
