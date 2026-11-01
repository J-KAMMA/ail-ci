# task: Implement a generator that yields the look-and-say sequence and print the first 10 terms.
from collections.abc import Iterator


def look_and_say() -> Iterator[str]:
    """Yield the terms of the look-and-say sequence, starting with '1'."""
    term = "1"
    while True:
        yield term
        parts: list[str] = []
        i = 0
        n = len(term)
        while i < n:
            digit = term[i]
            count = 1
            while i + count < n and term[i + count] == digit:
                count += 1
            parts.append(f"{count}{digit}")
            i += count
        term = "".join(parts)


def main() -> None:
    for index, term in enumerate(look_and_say(), start=1):
        if index > 10:
            break
        print(f"{index}: {term}")


if __name__ == "__main__":
    main()
