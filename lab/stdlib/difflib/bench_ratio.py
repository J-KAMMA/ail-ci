import difflib


def make_lines(seed):
    state = seed
    lines = []
    for i in range(3000):
        state = (state * 1103515245 + 12345) % 2147483648
        lines.append("row %d value %d" % (i, state % 100000))
    return lines


def main():
    a = make_lines(12345)
    b = make_lines(12345)
    i = 0
    while i < len(b):
        b[i] = b[i] + " changed"
        i = i + 10
    matcher = difflib.SequenceMatcher(None, a, b)
    print(round(matcher.ratio(), 6))
    print(len(matcher.get_opcodes()))


main()
