"""Driver for json_parse: parse one generated JSON document many times."""
import json_parse as m

ITEM = '{"id": 1234, "name": "widget", "tags": ["a", "b", "c"], "ok": true, "x": 1.5}'
REPEAT = 40000


def main() -> None:
    text = "[" + ",".join([ITEM] * REPEAT) + "]"
    tokens = m.count_tokens(text)
    depth = m.depth_of(text)
    digits = m.digits_in(text)
    size = m.document_bytes(text)
    total = 0
    for _ in range(3):
        p = m.Parser(text)
        total += p.parse_value()
    print("bytes", size)
    print("tokens", tokens)
    print("depth", depth)
    print("digits", digits)
    print("objects", total)


main()
