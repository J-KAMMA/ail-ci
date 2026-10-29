# task: Write a script that uses re.sub to mask all but the last four digits of hardcoded credit card numbers and prints the masked results.
import re


CARD_PATTERN: re.Pattern[str] = re.compile(r"\b[0-9](?:[ -]?[0-9]){11,18}\b")

SAMPLE_TEXT: list[str] = [
    "Visa: 4111 1111 1111 1111",
    "Mastercard 5500-0000-0000-0004",
    "Amex 3714 496353 98431",
    "Discover 6011000990139424",
    "Order id 12345 is not a card",
    "Phone 5551234567 is not a card",
    "Backup Visa 4012888888881881 expires 12/29",
]


def mask_card(match: re.Match[str]) -> str:
    """Mask every digit except the last four, preserving separators."""
    text: str = match.group(0)
    total_digits: int = sum(1 for ch in text if ch in "0123456789")
    visible_from: int = total_digits - 4
    seen: int = 0
    pieces: list[str] = []
    for ch in text:
        if ch in "0123456789":
            seen += 1
            pieces.append(ch if seen > visible_from else "*")
        else:
            pieces.append(ch)
    return "".join(pieces)


def main() -> None:
    for line in SAMPLE_TEXT:
        masked, count = CARD_PATTERN.subn(mask_card, line)
        print(f"Original: {line}")
        print(f"Masked:   {masked}")
        print(f"Cards masked: {count}")
        print()


if __name__ == "__main__":
    main()
