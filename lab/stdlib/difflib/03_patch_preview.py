import difflib


def show_patch(old_text, new_text, label):
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=label + "/old",
        tofile=label + "/new",
        fromfiledate="2024-01-01 10:00:00",
        tofiledate="2024-01-02 11:30:00",
        n=2,
        lineterm="",
    )
    for line in diff:
        print(line)


def main():
    old = "alpha\nbeta\ngamma\ndelta\nepsilon\nzeta\n"
    new = "alpha\nbeta changed\ngamma\ndelta\nepsilon\nzeta\neta\n"
    show_patch(old, new, "config")
    show_patch("one\ntwo\n", "one\ntwo\n", "same")
    show_patch("", "first\nsecond\n", "new")


main()
