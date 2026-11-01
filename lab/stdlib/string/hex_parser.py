import string

VALUES = ["ff", "0x1A", "deadBEEF", "", "xyz", "10"]


def parse(text):
    text = text.strip()
    if text.lower().startswith("0x"):
        text = text[2:]
    if not text:
        raise ValueError("empty number")
    for ch in text:
        if ch not in string.hexdigits:
            raise ValueError("bad digit " + repr(ch))
    return int(text, 16)


def main():
    for value in VALUES:
        try:
            print(repr(value), parse(value))
        except ValueError as exc:
            print(repr(value), "ValueError", exc)
    print(string.hexdigits)
    print(string.octdigits)


main()
