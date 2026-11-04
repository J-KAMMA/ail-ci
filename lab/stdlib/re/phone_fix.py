import re

PHONE = re.compile(r"\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})")


def normalize(text: str) -> str:
    m = PHONE.fullmatch(text)
    if m is None:
        return ""
    return "(" + m.group(1) + ") " + m.group(2) + "-" + m.group(3)


def main() -> int:
    for text in ["555-123-4567", "(555) 123 4567", "555.123.4567", "12-34", ""]:
        print(repr(text), "->", repr(normalize(text)))
    print(PHONE.sub(r"(\1) \2-\3", "call 555-123-4567 or 800.555.0199"))
    out, count = PHONE.subn(r"\1.\2.\3", "555-123-4567 800 555 0199")
    print(out, count)
    print(len(re.findall(r"\d{3}", "")))
    print(re.sub(r"\s+", "", "  a b  ", count=1))
    print(PHONE.search("no number here") is None)
    return 0


main()
