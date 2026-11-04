import difflib


def main():
    a = "qabxcd"
    b = "abycdf"
    matcher = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        print("%7s a[%d:%d] (%s) b[%d:%d] (%s)" % (tag, i1, i2, a[i1:i2], j1, j2, b[j1:j2]))
    blocks = matcher.get_matching_blocks()
    print(blocks)
    for block in blocks:
        print(block.a, block.b, block.size, block[0], len(block))
    print("longest:", matcher.find_longest_match(0, len(a), 0, len(b)))
    print("bounded:", matcher.find_longest_match(1, 4, 1, 5))
    print("none:", difflib.SequenceMatcher(None, "ab", "c").find_longest_match(0, 2, 0, 1))


main()
