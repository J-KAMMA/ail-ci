import token


def main() -> None:
    print("N_TOKENS", token.N_TOKENS)
    print("table size", len(token.tok_name))
    for value in sorted(token.tok_name):
        name = token.tok_name[value]
        marker = "terminal"
        if token.ISNONTERMINAL(value):
            marker = "nonterminal"
        if token.ISEOF(value):
            marker = "eof"
        print(name, value, marker)
    print("exact", len(token.EXACT_TOKEN_TYPES))


main()
