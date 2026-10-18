import sys


def shift_char(ch: str, k: int) -> str:
    if "A" <= ch <= "Z":
        return chr((ord(ch) - ord("A") + k) % 26 + ord("A"))
    if "a" <= ch <= "z":
        return chr((ord(ch) - ord("a") + k) % 26 + ord("a"))
    return ch


def caesar(text: str, k: int) -> str:
    return "".join(shift_char(ch, k) for ch in text)


def main() -> None:
    first = sys.stdin.readline()
    if first == "":
        return
    k = int(first.strip())
    text = sys.stdin.read()

    result = caesar(text, k)
    print(result)
    if caesar(result, -k) == text:
        print("ok")


if __name__ == "__main__":
    main()
