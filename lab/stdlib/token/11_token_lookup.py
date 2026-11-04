import token


def describe(n: int) -> str:
    name = token.tok_name.get(n, "?")
    if token.ISEOF(n):
        kind = "eof"
    elif token.ISTERMINAL(n):
        kind = "terminal"
    elif token.ISNONTERMINAL(n):
        kind = "nonterminal"
    else:
        kind = "unknown"
    return name + "/" + kind


def main() -> None:
    for n in [token.NAME, token.NUMBER, token.STRING, token.OP, token.ENDMARKER,
              token.ERRORTOKEN, token.NT_OFFSET]:
        print(n, describe(n))
    print("missing", token.tok_name.get(9999, "absent"))
    print("named", token.tok_name[token.NAME], token.tok_name[token.ENDMARKER])


main()
