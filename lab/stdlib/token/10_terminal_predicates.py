import token


def main() -> None:
    values = [token.ENDMARKER, token.NAME, token.OP, token.NUMBER, token.NT_OFFSET,
              token.NT_OFFSET + 1, token.N_TOKENS]
    for value in values:
        print(value, token.ISTERMINAL(value), token.ISNONTERMINAL(value), token.ISEOF(value))
    print("name terminal", token.ISTERMINAL(token.NAME))
    print("op terminal", token.ISTERMINAL(token.OP))
    print("eof", token.ISEOF(token.ENDMARKER), token.ISEOF(token.NAME))
    print("nonterminal", token.ISNONTERMINAL(token.NT_OFFSET), token.ISNONTERMINAL(256))


main()
