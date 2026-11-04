import re

SECRET = re.compile(r"(?P<user>[A-Za-z0-9._%+-]+)@(?P<domain>[A-Za-z0-9.-]+)")


def mask(m: re.Match[str]) -> str:
    return m.group("user")[:1] + "***@" + m.group("domain")


def main() -> int:
    text = "mail a@example.com or bob.smith@example.org"
    print(SECRET.sub(mask, text))
    for m in SECRET.finditer(text):
        print(m.group(1), m.group(2))
    m = SECRET.search(text)
    if m:
        print(m.group(1, 2))
    print(SECRET.subn(lambda m: m.group(0).upper(), text))
    print(len(SECRET.findall("")))
    print(SECRET.pattern)
    return 0


main()
