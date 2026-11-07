# task: Use itertools.groupby on a hardcoded sorted string to run-length encode it and print the encoded result.
import itertools


def run_length_encode(text: str) -> str:
    """Run-length encode a string using itertools.groupby."""
    parts: list[str] = []
    for char, group in itertools.groupby(text):
        count = sum(1 for _ in group)
        parts.append(f"{count}{char}")
    return "".join(parts)


def main() -> None:
    # Hardcoded sorted string (characters grouped into runs).
    sorted_text: str = "aaabbbbccdddddeffff"
    encoded: str = run_length_encode(sorted_text)
    print(f"Original: {sorted_text}")
    print(f"Encoded:  {encoded}")


if __name__ == "__main__":
    main()
