"""Longest common subsequence: length and one subsequence, with backtracking."""
import sys

SMALL = "--small" in sys.argv
STR_LEN = 60 if SMALL else 2200
PAIRS = 2 if SMALL else 3

seed = 777


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def text(length, alphabet):
    chars = []
    for _ in range(length):
        chars.append(alphabet[rnd() % len(alphabet)])
    return "".join(chars)


def lcs(a, b):
    m = len(a)
    n = len(b)
    table = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        ai = a[i - 1]
        row = table[i]
        previous = table[i - 1]
        for j in range(1, n + 1):
            if ai == b[j - 1]:
                row[j] = previous[j - 1] + 1
            elif previous[j] >= row[j - 1]:
                row[j] = previous[j]
            else:
                row[j] = row[j - 1]
    out = []
    i = m
    j = n
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out.append(a[i - 1])
            i -= 1
            j -= 1
        elif table[i - 1][j] >= table[i][j - 1]:
            i -= 1
        else:
            j -= 1
    out.reverse()
    return table[m][n], "".join(out)


checksum = 0
for case in range(PAIRS):
    left = text(STR_LEN, "abcd")
    right = text(STR_LEN, "abcd")
    length, sequence = lcs(left, right)
    checksum += length
    print("case", case, "length", length, "sample", sequence[:32])

print("checksum", checksum)
