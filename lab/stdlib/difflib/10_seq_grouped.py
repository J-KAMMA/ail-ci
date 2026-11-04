import difflib


def main():
    a = [str(i) for i in range(1, 40)]
    b = a[:]
    b[8:8] = ["i"]
    b[20] += "x"
    b[23:28] = []
    b[30] += "y"
    matcher = difflib.SequenceMatcher(None, a, b)
    for group in matcher.get_grouped_opcodes():
        print(group)
    print("n=1")
    for group in matcher.get_grouped_opcodes(1):
        print(group)
    nums_a = [0, 1, 2, 0, 3, 4, 0]
    nums_b = [0, 1, 9, 0, 3, 4, 0]
    plain = difflib.SequenceMatcher(None, nums_a, nums_b)
    junked = difflib.SequenceMatcher(lambda x: x == 0, nums_a, nums_b, autojunk=False)
    print("plain:", plain.ratio(), plain.get_opcodes())
    print("junked:", junked.ratio(), junked.get_opcodes())


main()
