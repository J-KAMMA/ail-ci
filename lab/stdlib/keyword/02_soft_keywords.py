import keyword


def main() -> None:
    print("count", len(keyword.softkwlist))
    print("all", keyword.softkwlist)
    for name in keyword.softkwlist:
        print("soft", name, keyword.issoftkeyword(name))
    for name in ["match", "case", "_", "type"]:
        print("use", name, keyword.issoftkeyword(name))
    for name in ["if", "for", "foo", "", "Match", "type_", "matchx"]:
        print("no", name, keyword.issoftkeyword(name))
    print("keyword is not soft", keyword.issoftkeyword("def"), keyword.issoftkeyword("None"))


main()
