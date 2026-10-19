import sys


def shift_char(c: str, k: int) -> str:
    """Shift a single ASCII letter by k positions, preserving case."""
    if "a" <= c <= "z":
        return chr((ord(c) - ord("a") + k) % 26 + ord("a"))
    if "A" <= c <= "Z":
        return chr((ord(c) - ord("A") + k) % 26 + ord("A"))
    return c


def caesar(text: str, k: int) -> str:
    """Apply a Caesar cipher with shift k to all ASCII letters in text."""
    return "".join(shift_char(c, k) for c in text)


def main() -> None:
    data = sys.stdin.read()
    first, _, rest = data.partition("\n")
    k = int(first.strip() or "0")
    text = "\n".join(rest.splitlines())

    encrypted = caesar(text, k)
    print(encrypted)

    decrypted = caesar(encrypted, -k)
    if decrypted == text:
        print("ok")


if __name__ == "__main__":
    main()
