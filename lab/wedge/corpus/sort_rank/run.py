"""Driver for sort_rank: rank a generated word stream."""
import sort_rank as m

CAP = 26
SIZE = 1600000
TOP = 24


def make_words(size: int) -> list[str]:
    bases = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
             "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi"]
    out = []
    i = 0
    while i < size:
        out.append(bases[i % 16] + str(i % 97))
        i += 1
    return out


def main() -> None:
    words = make_words(SIZE)
    counts = m.count_terms(words, CAP)
    top = m.top_indices(counts, TOP)
    print("words", len(words))
    print("total", m.total_count(counts))
    print("max", m.max_count(counts))
    print("above", m.count_above(counts, 1))
    print("top", top[:8])
    print("topscore", m.top_score(counts, TOP))
    print("spread", m.hash_spread(words, CAP, 16))


main()
