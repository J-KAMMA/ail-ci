import keyword


NAMES = ["False", "None", "True", "match", "case", "_", "type", "if", "while", "print", ""]


def classify(name: str) -> str:
    if keyword.iskeyword(name):
        return "keyword"
    if keyword.issoftkeyword(name):
        return "soft"
    return "name"


def main() -> None:
    table = []
    for name in NAMES:
        table.append((name, classify(name)))
    for name, kind in table:
        print(name, kind)
    both = [n for n in NAMES if keyword.iskeyword(n) or keyword.issoftkeyword(n)]
    print("both", both)
    print("rows", len(table))


main()
