import sys


def main() -> None:
    lines = sys.stdin.read().splitlines()
    first = [int(x) for x in lines[0].split()] if len(lines) > 0 else []
    second = [int(x) for x in lines[1].split()] if len(lines) > 1 else []

    second_set = set(second)
    diff = [x for x in first if x not in second_set]

    set_a = set(first)
    set_b = second_set
    common = set_a & set_b
    union = set_a | set_b
    jaccard = len(common) / len(union) if union else 0.0

    print(" ".join(map(str, diff)))
    print(len(common))
    print(f"{jaccard:.4f}")


if __name__ == "__main__":
    main()
