import textwrap

CONFIG = """\
    name = demo
      retries = 3
    timeout = 30
"""


def main() -> None:
    print(textwrap.dedent(CONFIG))
    body = textwrap.dedent("""
        line one
        line two
          nested
    """).strip()
    print(textwrap.indent(body, "    "))
    print(repr(textwrap.dedent("\t a\n\t b\n  \n\t  c")))
    print(repr(textwrap.dedent("  x\n y")))
    print(repr(textwrap.dedent("")))
    print(repr(textwrap.indent("a\n\nb\n", "> ")))


main()
