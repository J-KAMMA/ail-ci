def main() -> None:
    xs = [i * i for i in range(6)]
    ys = [x + 1 for x in xs if x % 2 == 0]
    total = sum(ys)
    print(xs, ys, total)
    names = ["a", "b", "c"]
    joined = "-".join(names)
    print(joined, len(joined))
    parts = joined.split("-")
    print(len(parts))


main()
