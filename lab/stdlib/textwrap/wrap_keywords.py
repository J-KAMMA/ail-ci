import textwrap

NOTES = [
    "Remember to run the focused tests before committing the change.",
    "The manifest must be regenerated after adding a new file.",
    "Keep the pull request small and describe the remaining refusals.",
]


def main() -> None:
    for note in NOTES:
        print(textwrap.fill(note, width=38, initial_indent="  ",
                            subsequent_indent="    "))
    lines = textwrap.wrap("alpha beta gamma delta", width=14,
                          subsequent_indent="> ")
    print(lines)
    print(textwrap.wrap("a b", width=20, initial_indent="[",
                        subsequent_indent="]"))
    print(textwrap.fill("one two", width=9, initial_indent="# "))
    print(textwrap.wrap("one two three", width=9, initial_indent="", subsequent_indent="."))


main()
