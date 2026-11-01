import string

LINES = [
    "Hello,   world!!!",
    "\tTabs\tand\nnewlines",
    "keep-hyphens_and_underscores",
    "dots... and commas,,,",
    "",
]


def sanitize(text):
    kept = []
    for ch in text:
        if ch in string.printable and ch not in string.punctuation:
            kept.append(ch)
        elif ch in string.whitespace:
            kept.append(" ")
    return " ".join("".join(kept).split())


def main():
    for line in LINES:
        print(repr(sanitize(line)))
    print("printable chars", len(string.printable))
    print("punct chars", len(string.punctuation))
    print("ascii letters", string.ascii_letters[:13], string.ascii_letters[13:])


main()
