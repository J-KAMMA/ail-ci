import token


def main() -> None:
    ops = ["+=", "+", "==", "**=", "->", "...", ":=", "@", "//="]
    for op in ops:
        print(op, token.EXACT_TOKEN_TYPES[op])
    value = token.EXACT_TOKEN_TYPES["+="]
    print("plus assign", value, token.tok_name[value])
    print("count", len(token.EXACT_TOKEN_TYPES))
    print("has", "+=" in token.EXACT_TOKEN_TYPES)
    print("missing", "%" in token.EXACT_TOKEN_TYPES, "**" in token.EXACT_TOKEN_TYPES)


main()
