import re

TOKEN = re.compile(r"\s*(?:(?P<num>\d+)|(?P<name>[A-Za-z_]\w*)|(?P<op>==|!=|<=|>=|[-+*/()]))")


def main() -> int:
    text = "x1 = 12 + y2*(3 - 4)"
    pos = 0
    kinds = []
    while pos < len(text):
        m = TOKEN.match(text[pos:])
        if m is None:
            break
        if m.group("num") is not None:
            kinds.append(("num", m.group("num")))
        elif m.group("name") is not None:
            kinds.append(("name", m.group("name")))
        else:
            kinds.append(("op", m.group("op")))
        pos += m.end(0)
    for kind, value in kinds:
        print(kind, value)
    print("count", len(kinds), "rest", repr(text[pos:]))
    for name, number in re.findall(r"([A-Za-z_]\w*)=(\d+)", "a=1 bb=22 c=x d=4"):
        print(name, int(number) + 1)
    print(len(re.findall(r"\d+", text)), len(re.findall(r"[A-Za-z_]\w*", text)))
    for m in re.finditer(r"[0-9]+", text):
        print("span", m.start(0), m.end(0))
    return 0


main()
