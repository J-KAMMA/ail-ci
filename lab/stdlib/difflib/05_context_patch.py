import difflib


def show(old, new, n):
    for line in difflib.context_diff(
        old,
        new,
        fromfile="before.txt",
        tofile="after.txt",
        fromfiledate="2024-03-01",
        tofiledate="2024-03-02",
        n=n,
        lineterm="",
    ):
        print(line)


def main():
    old = "red\ngreen\nblue\nyellow\nblack\nwhite\n".splitlines()
    new = "red\ngreen\ncyan\nyellow\nblack\nwhite\npurple\n".splitlines()
    show(old, new, 1)
    show(old, old, 3)
    show([], ["only"], 3)
    print(list(difflib.context_diff(["same"], ["same"], n=0)))


main()
