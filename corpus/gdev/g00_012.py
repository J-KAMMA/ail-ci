# task: Write a script that encrypts a hardcoded plaintext with a Vigenère cipher using a fixed keyword and prints the result.
from typing import Final


PLAINTEXT: Final[str] = "Attack at dawn! The quick brown fox jumps over the lazy dog."
KEYWORD: Final[str] = "LEMON"


def vigenere_encrypt(plaintext: str, keyword: str) -> str:
    """Encrypt plaintext with the Vigenere cipher; non-letters are preserved."""
    key: str = keyword.upper()
    if not key or not all(ch.isalpha() and ch.isascii() for ch in key):
        raise ValueError("keyword must be a non-empty ASCII alphabetic string")

    result: list[str] = []
    key_index: int = 0
    key_len: int = len(key)

    for ch in plaintext:
        if ch.isascii() and ch.isalpha():
            base: int = ord("A") if ch.isupper() else ord("a")
            shift: int = ord(key[key_index % key_len]) - ord("A")
            encrypted: int = (ord(ch) - base + shift) % 26
            result.append(chr(base + encrypted))
            key_index += 1
        else:
            result.append(ch)

    return "".join(result)


def main() -> None:
    ciphertext: str = vigenere_encrypt(PLAINTEXT, KEYWORD)
    print(f"Plaintext:  {PLAINTEXT}")
    print(f"Keyword:    {KEYWORD}")
    print(f"Ciphertext: {ciphertext}")


if __name__ == "__main__":
    main()
