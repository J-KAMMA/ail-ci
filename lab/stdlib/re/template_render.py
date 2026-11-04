import re

SLOT = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, values: dict[str, str]) -> str:
    def lookup(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        return "?" + key

    return SLOT.sub(lookup, template)


def main() -> int:
    text = "Hello {{name}}, you have {{count}} messages"
    print(render(text, {"name": "Ada", "count": "3"}))
    print(render(text, {}))
    print(SLOT.sub(r"<\1>", text))
    print(SLOT.subn(r"[\g<1>]", text, 1))
    print(SLOT.findall(text))
    print(re.sub(r"(\w+)\s+(\w+)", r"\2 \1", "one two three four", count=2))
    print(re.sub(r"\s+", " ", "  a   b  "))
    return 0


main()
