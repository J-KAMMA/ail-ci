import textwrap

MESSAGES = [
    "The deployment finished successfully on every host in the cluster.",
    "One worker reported a warning that should be reviewed by an operator.",
    "Short message.",
]


def main() -> None:
    for message in MESSAGES:
        print(textwrap.fill(message, width=32, max_lines=2))
        print(textwrap.fill(message, width=32, max_lines=2,
                            placeholder=" ..."))
    try:
        print(textwrap.fill("word " * 10, width=6, max_lines=1,
                            placeholder="[...]"))
    except ValueError as exc:
        print("ValueError", exc)
    print(textwrap.wrap("one two three four five", width=14, max_lines=2,
                        placeholder=" ..."))


main()
