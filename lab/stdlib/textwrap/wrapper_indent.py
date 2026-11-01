from textwrap import TextWrapper

BULLETS = [
    "Write the smallest change that fixes the reported problem.",
    "Add a regression test that fails before the fix and passes after it.",
    "Keep the generated C identical for the frozen comparison tasks.",
    "Record every remaining refusal with its exact message.",
]


def main() -> None:
    wrapper = TextWrapper(width=46, initial_indent="* ", subsequent_indent="  ")
    for item in BULLETS:
        print(wrapper.fill(item))
    print(wrapper.wrap(BULLETS[0]))
    print(wrapper.width)
    print(repr(wrapper.initial_indent))
    print(repr(wrapper.subsequent_indent))


main()
