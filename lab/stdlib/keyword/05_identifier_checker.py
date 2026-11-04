import keyword


def is_identifier(s: str) -> bool:
    if s == "":
        return False
    first = s[0]
    if not (first.isalpha() or first == "_"):
        return False
    i = 1
    while i < len(s):
        c = s[i]
        if not (c.isalpha() or c == "_" or c.isdigit()):
            return False
        i = i + 1
    return True


def check(s: str) -> str:
    if not is_identifier(s):
        return "not-identifier"
    if keyword.iskeyword(s):
        return "keyword"
    if keyword.issoftkeyword(s):
        return "soft-keyword"
    return "identifier"


def main() -> None:
    for s in ["name", "class", "match", "1bad", "", "_", "if_", "type", "has space"]:
        print(s, check(s))
    good = [s for s in ["x", "y", "for", "1z", "match"] if is_identifier(s) and not keyword.iskeyword(s)]
    print("good", good)
    print("checks", is_identifier("name"), is_identifier("1bad"), is_identifier(""))


main()
