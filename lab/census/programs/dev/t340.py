import sys


def generate_parentheses(pairs: int) -> list[str]:
    """Return all balanced parentheses strings with the given number of pairs."""
    results: list[str] = []

    def build(current: list[str], opened: int, closed: int) -> None:
        if opened == pairs and closed == pairs:
            results.append("".join(current))
            return
        if opened < pairs:
            current.append("(")
            build(current, opened + 1, closed)
            current.pop()
        if closed < opened:
            current.append(")")
            build(current, opened, closed + 1)
            current.pop()

    build([], 0, 0)
    return results


def main() -> None:
    n = int(sys.stdin.readline().strip())
    m = min(n, 6)
    strings = sorted(generate_parentheses(m))
    print(len(strings))
    for s in strings[:3]:
        print(s)


if __name__ == "__main__":
    main()
