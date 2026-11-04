# task: Recursively generate all binary strings of length 4 that contain no two consecutive 1s and print them with their count.
def generate(length: int, prefix: str = "") -> list[str]:
    """Recursively build all binary strings of the given length with no two consecutive 1s."""
    if len(prefix) == length:
        return [prefix]

    results: list[str] = []
    # Always allowed to append a 0.
    results.extend(generate(length, prefix + "0"))
    # Append a 1 only if the previous character is not already a 1.
    if not prefix.endswith("1"):
        results.extend(generate(length, prefix + "1"))
    return results


def main() -> None:
    strings: list[str] = generate(4)
    for s in strings:
        print(s)
    print(f"Count: {len(strings)}")


if __name__ == "__main__":
    main()
