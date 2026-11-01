import re

LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def main() -> int:
    text = "See [docs](https://example.com/a) and [mail](mailto:x@example.org)."
    for m in LINK.finditer(text):
        print(m.group(1), "->", m.group(2), m.span())
    print(LINK.sub(lambda m: m.group(1).upper() + " <" + m.group(2) + ">", text))
    m = LINK.search(text)
    if m:
        a, b = m.span()
        print(a, b, text[a:b])
        print(m.start(1), m.end(2))
    print(LINK.findall(""))
    print(LINK.sub(r"\2#\1", text, count=1))
    print(re.sub(r"https?://", "", "https://example.com http://example.org"))
    return 0


main()
