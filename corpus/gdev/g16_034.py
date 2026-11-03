# task: Use enumerate with a generator expression to yield the position and text of each word longer than four characters in a fixed sentence and print them.
from typing import Iterator


SENTENCE: str = (
    "The quick brown fox jumps over the lazy dog while seven wizards "
    "quietly juggle bright glass orbs near the old stone bridge"
)


def long_words(text: str) -> Iterator[tuple[int, str]]:
    """Yield (position, word) for each word longer than four characters."""
    return (
        (position, word)
        for position, word in enumerate(text.split())
        if len(word) > 4
    )


def main() -> None:
    for position, word in long_words(SENTENCE):
        print(f"{position}: {word}")


if __name__ == "__main__":
    main()
