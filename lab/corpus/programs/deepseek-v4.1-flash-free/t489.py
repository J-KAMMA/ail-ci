import sys
import unicodedata


def main() -> None:
    text = sys.stdin.read()
    codepoints = sorted({ch for ch in text if ord(ch) > 127}, key=ord)
    for ch in codepoints:
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "unnamed"
        category = unicodedata.category(ch)
        nfc = len(unicodedata.normalize("NFC", ch))
        nfd = len(unicodedata.normalize("NFD", ch))
        print(f"U+{ord(ch):04X} {category} {name} {nfc}/{nfd}")


if __name__ == "__main__":
    main()
