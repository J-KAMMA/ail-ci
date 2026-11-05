"""Levenshtein edit distance over many generated word pairs."""
import sys

SMALL = "--small" in sys.argv
PAIRS = 180 if SMALL else 1500
WORD_LEN = 18 if SMALL else 68

seed = 20240517


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def word(length):
    letters = []
    for _ in range(length):
        letters.append(chr(97 + rnd() % 26))
    return "".join(letters)


def distance(a, b):
    rows = len(a) + 1
    cols = len(b) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + cost,
            )
    return table[rows - 1][cols - 1]


total = 0
lowest = None
highest = 0
for _ in range(PAIRS):
    left = word(WORD_LEN)
    right = word(WORD_LEN)
    d = distance(left, right)
    total += d
    if lowest is None or d < lowest:
        lowest = d
    if d > highest:
        highest = d

print("pairs", PAIRS)
print("checksum", total)
print("min", lowest)
print("max", highest)
