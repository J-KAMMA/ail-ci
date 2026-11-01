import difflib


def main():
    old = ["alpha\n", "\n", "# note\n", "beta value\n", "gamma\n"]
    new = ["alpha\n", "\n", "beta values\n", "gamma\n", "# note\n"]
    print("plain:")
    for line in difflib.Differ().compare(old, new):
        print(line, end="")
    print("junk aware:")
    differ = difflib.Differ(linejunk=difflib.IS_LINE_JUNK, charjunk=difflib.IS_CHARACTER_JUNK)
    for line in differ.compare(old, new):
        print(line, end="")
    for text in ["\n", "  #  \n", "# not junk\n", "x\n"]:
        print(repr(text), difflib.IS_LINE_JUNK(text))
    print(difflib.IS_CHARACTER_JUNK(" "), difflib.IS_CHARACTER_JUNK("\t"), difflib.IS_CHARACTER_JUNK("\n"))


main()
