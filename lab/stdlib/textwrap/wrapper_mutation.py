from textwrap import TextWrapper


def main() -> None:
    wrapper = TextWrapper(width=40)
    print(wrapper.fill("The first paragraph is short."))
    wrapper.width = 18
    print(wrapper.wrap("The second paragraph is a little longer."))
    wrapper.initial_indent = ">> "
    wrapper.subsequent_indent = "   "
    print(wrapper.fill("The third paragraph keeps going for a while."))
    wrapper.width = 70
    print(wrapper.fill("Back to a wide line."))
    print(wrapper.width, repr(wrapper.initial_indent),
          repr(wrapper.subsequent_indent))
    wrapper.break_long_words = False
    print(wrapper.wrap("antidisestablishmentarianism"))


main()
