import token


def main() -> None:
    print("ENDMARKER", token.ENDMARKER)
    print("NAME", token.NAME)
    print("NUMBER", token.NUMBER)
    print("OP", token.OP)
    print("N_TOKENS", token.N_TOKENS)
    print("names", token.tok_name[token.NAME], token.tok_name[token.NUMBER], token.tok_name[token.OP])
    print("end", token.tok_name[token.ENDMARKER])
    print("count", len(token.tok_name))


main()
