"""Driver for edit_dist: Levenshtein distance over pairs of words."""
import edit_dist as m

WORD = "abcdefghijklmnopqrstuvwxyz"
VARIANTS = [
    "abcdefghijklmnopqrstuvwxy",
    "abcdefghijklmnopqrstuvwxyzz",
    "abcdefghijklmnopqrstuvwxzz",
    "abcdefghijklmnopqrstuvwxyy",
    "bacdefghijklmnopqrstuvwxyz",
]
ROUNDS = 800


def main() -> None:
    total = 0
    pref = 0
    bigrams = 0
    ham = 0
    best = 0
    for _r in range(ROUNDS):
        for v in VARIANTS:
            total += m.levenshtein(WORD, v)
            pref += m.common_prefix(WORD, v)
            bigrams += m.bigram_overlap(WORD, v)
            ham += m.hamming(WORD, v)
            best += m.best_match(WORD, VARIANTS)
    print("length", m.total_length(VARIANTS))
    print("distance", total)
    print("prefix", pref)
    print("bigrams", bigrams)
    print("hamming", ham)
    print("best", best)


main()
