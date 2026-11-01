import string

ROWS = [("Ada", 36), ("Grace", 85), ("Edsger", 72)]


def main():
    fmt = string.Formatter()
    template = "{name:<10}{score:>5}\n"
    print(template.format(name="NAME", score="SCORE"), end="")
    for name, score in ROWS:
        print(fmt.format(template, name=name, score=score), end="")
    print(fmt.format("{0!r} {1:.2f}", "pi", 3.14159))
    for literal, field, spec, conversion in fmt.parse("{name:>6} {value!r}"):
        print(repr(literal), repr(field), repr(spec), repr(conversion))
    print(fmt.get_value("x", (), {"x": 7}))
    print(fmt.get_field("a.b", (), {"a": type("Box", (), {"b": 9})()}))


main()
