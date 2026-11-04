import keyword


def main() -> None:
    for name in keyword.kwlist:
        if not keyword.iskeyword(name):
            print("missing", name)
    for name in ["if", "def", "class", "None", "True", "async", "await", "yield"]:
        print("keyword", name, keyword.iskeyword(name))
    for name in ["match", "case", "_", "type", "foo", "If", "if_", "", "NoneType"]:
        print("plain", name, keyword.iskeyword(name))
    print("both", keyword.iskeyword("if"), keyword.issoftkeyword("if"))


main()
