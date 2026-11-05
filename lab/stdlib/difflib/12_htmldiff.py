import difflib


def main():
    old = ["red\n", "green\n", "blue\n"]
    new = ["red\n", "GREEN\n", "blue\n", "black\n"]
    table = difflib.HtmlDiff().make_table(old, new, fromdesc="before", todesc="after")
    print(table[:120])
    page = difflib.HtmlDiff(wrapcolumn=60).make_file(old, new, "before.txt", "after.txt")
    print(len(page))


main()
