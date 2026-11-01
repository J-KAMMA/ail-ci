import re

PAIR = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*$")
COMMENT = re.compile(r"(^|\s)#.*$")


def main() -> int:
    text = """
    name = demo
    count = 3
    # a comment
    path = /tmp/example
    empty =
    """
    values = {}
    for line in text.splitlines():
        line = COMMENT.sub("", line)
        if not line.strip():
            continue
        pairs = PAIR.findall(line)
        for key, value in pairs:
            values[key] = value
    for key in sorted(values):
        print(key, repr(values[key]))
    print(len(values))
    print(PAIR.match("  x = y").group(2))
    print(COMMENT.sub("", "a # b"))
    return 0


main()
