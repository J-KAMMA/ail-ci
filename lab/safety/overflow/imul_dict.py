def main() -> None:
    counts = {"total": 1}
    for i in range(4):
        counts["total"] *= 2
    print(counts["total"])
    for i in range(58):
        counts["total"] *= 2
    print(counts["total"])
    for i in range(1):
        counts["total"] += counts["total"]
    print(counts["total"])


main()
