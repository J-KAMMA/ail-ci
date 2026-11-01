import textwrap


def main() -> None:
    for width in (0, -1, -70):
        try:
            textwrap.wrap("a b", width)
        except ValueError as exc:
            print("wrap", width, type(exc).__name__, str(exc))
        try:
            textwrap.fill("a b", width)
        except ValueError as exc:
            print("fill", width, type(exc).__name__, str(exc))
    print(textwrap.wrap("", 10))
    print(textwrap.wrap("   ", 10))
    print(textwrap.fill("", 10))
    print(textwrap.wrap("a", 1))
    print(textwrap.wrap("ab", 1))
    try:
        textwrap.shorten("a b c d", 4)
    except ValueError as exc:
        print("shorten", type(exc).__name__, str(exc))
    wrapper = textwrap.TextWrapper(width=10)
    print(wrapper.wrap(""))
    print(wrapper.wrap("   "))
    print(wrapper.fill("a b"))


main()
