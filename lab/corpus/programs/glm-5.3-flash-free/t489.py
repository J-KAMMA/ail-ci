import sys
import unicodedata


def analyze(text: str) -> list[tuple[str, str, str, int, int]]:
    results: list[tuple[str, str, str, int, int]] = []
    chars = {ch for ch in text if ord(ch) >= 0x80}
    for ch in sorted(chars, key=ord):
        name: str = unicodedata.name(ch, "unnamed")
        nfc: str = unicodedata.normalize("NFC", ch)
        nfd: str = unicodedata.normalize("NFD", ch)
        code = f"U+{ord(ch):04X}"
        results.append((code, unicodedata.category(ch), name, len(nfc), len(nfd)))
    return results


def main() -> None:
    text: str = sys.stdin.read()
    for code, category, name, nfc_len, nfd_len in analyze(text):
        print(f"{code} {category} {name} nfc={nfc_len} nfd={nfd_len}")


if __name__ == "__main__":
    main()
