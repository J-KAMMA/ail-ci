def main() -> None:
    n = int(input())
    values = [int(x) for x in input().split()]
    changed = sum(1 for v in values if v < 0)
    result = [abs(v) for v in values]
    print(" ".join(map(str, result)))
    print(changed)


if __name__ == "__main__":
    main()
