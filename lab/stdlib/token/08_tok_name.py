import token


def main() -> None:
    names = sorted(token.tok_name)
    for name in names:
        print(name, token.tok_name[name])
    print("total", len(names))
    print("first", names[0])
    print("last", names[-1])


main()
