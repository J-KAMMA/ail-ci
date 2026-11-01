import textwrap

TEXT = "alpha\tbeta gamma\ndelta epsilon"


def main() -> None:
    print(repr(textwrap.fill(TEXT, width=18)))
    print(repr(textwrap.fill(TEXT, width=18, expand_tabs=False)))
    print(repr(textwrap.fill(TEXT, width=18, tabsize=4)))
    print(repr(textwrap.fill(TEXT, width=18, replace_whitespace=False)))
    print(repr(textwrap.fill(TEXT, width=18, drop_whitespace=False)))
    print(repr(textwrap.fill("  padded  text  ", width=8,
                             drop_whitespace=False)))
    wrapper = textwrap.TextWrapper(width=12, expand_tabs=False,
                                   replace_whitespace=False, tabsize=2)
    print(repr(wrapper.fill(TEXT)))
    print(repr(textwrap.fill("a\tb", width=5, tabsize=0)))
    print(repr(textwrap.fill("a\tb", width=5, tabsize=3)))


main()
