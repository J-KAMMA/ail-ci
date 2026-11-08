"""Driver for tokenizer: lex a generated source file repeatedly."""
import tokenizer as m

SIZE = 40000
LINE = "def alpha_beta(gamma, delta_1):\n    return gamma + delta_1 * 42  # note\n"


def main() -> None:
    src = LINE * SIZE
    words = m.count_idents(src)
    longest = m.longest_ident(src)
    defs = m.count_keywords(src, "def")
    digits = m.digit_count(src)
    weight = m.token_weight(src)
    starts = 0
    for ch in src[:200000]:
        if m.is_ident_start(ch):
            starts += 1
    print("idents", words)
    print("longest", longest)
    print("defs", defs)
    print("digits", digits)
    print("weight", weight)
    print("starts", starts)


main()
