# task: Build a Morse code dictionary for a subset of letters and encode a fixed message, printing the result.
from typing import Final

MORSE_SUBSET: Final[dict[str, str]] = {
    "S": "...",
    "O": "---",
    "E": ".",
    "T": "-",
    "A": ".-",
    "N": "-.",
    "H": "....",
    "I": "..",
    "M": "--",
    "R": ".-.",
}

MESSAGE: Final[str] = "SOS THE MINE RAN"


def encode(message: str, table: dict[str, str]) -> list[str]:
    """Encode a message into Morse code groups, one group per word."""
    words: list[str] = []
    for word in message.upper().split():
        codes: list[str] = []
        for ch in word:
            if ch in table:
                codes.append(table[ch])
            else:
                codes.append("?")
        words.append(" ".join(codes))
    return words


def main() -> None:
    table: dict[str, str] = dict(sorted(MORSE_SUBSET.items()))

    print("Morse dictionary (sorted by letter):")
    for letter, code in table.items():
        print(f"  {letter} -> {code}")

    print()
    print(f"Message: {MESSAGE}")
    encoded_words: list[str] = encode(MESSAGE, table)
    print("Encoded:", " / ".join(encoded_words))


if __name__ == "__main__":
    main()
