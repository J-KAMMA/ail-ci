# task: Write a script that decodes a hardcoded run-length encoded string back to its original form and prints it.
from typing import Final

ENCODED: Final[str] = "12W1B12W3B24W1B14W"


def decode_rle(encoded: str) -> str:
    """Decode a run-length encoded string made of <count><char> pairs."""
    parts: list[str] = []
    count_digits: str = ""

    for ch in encoded:
        if "0" <= ch <= "9":
            count_digits += ch
        else:
            if not count_digits:
                raise ValueError(f"missing count before {ch!r}")
            parts.append(ch * int(count_digits))
            count_digits = ""

    if count_digits:
        raise ValueError("trailing count without a character")

    return "".join(parts)


def main() -> None:
    decoded: str = decode_rle(ENCODED)
    print(decoded)


if __name__ == "__main__":
    main()
