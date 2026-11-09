"""difflib fuzzy matching vs rapidfuzz (Rust/C++) on the same pairs and candidate lists.

CPython and hybrid both use difflib, so their stdout must match byte for byte.  rapidfuzz is a
separate implementation with a slightly different string metric; it is the rewrite baseline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _impl import LCG, impl, load_hybrid  # noqa: E402

PAIRS = 60000
CANDIDATE_LISTS = 1200
LIST_LEN = 60
ALPHABET = 'abcdefghijklmnopqrstuvwxyz '


def word(rng, n):
    return ''.join(ALPHABET[rng.below(len(ALPHABET))] for _ in range(n))


def inputs():
    rng = LCG(515151)
    pairs = [(word(rng, 4 + rng.below(24)), word(rng, 4 + rng.below(24)))
             for _ in range(PAIRS)]
    lists = []
    for _ in range(CANDIDATE_LISTS):
        base = word(rng, 6 + rng.below(14))
        cands = []
        for _ in range(LIST_LEN):
            if rng.below(2):
                pos = rng.below(len(base))
                cands.append(base[:pos] + ALPHABET[rng.below(len(ALPHABET))] + base[pos + 1:])
            else:
                cands.append(word(rng, 6 + rng.below(14)))
        lists.append((base, cands))
    return pairs, lists


def main():
    mode = impl()
    pairs, lists = inputs()

    if mode == 'rust':
        from rapidfuzz import fuzz, process
        total = 0
        for a, b in pairs:
            total += int(round(fuzz.ratio(a, b) * 10))
        matches = 0
        mtotal = 0
        for w, cands in lists:
            found = process.extract(w, cands, scorer=fuzz.ratio, score_cutoff=60, limit=3)
            matches += len(found)
            mtotal += sum(int(round(score * 10)) for _, score, _ in found)
        print('pairs', len(pairs), 'total', total, 'matches', matches, 'mtotal', mtotal)
        return

    import difflib
    if mode == 'hybrid':
        difflib = load_hybrid('difflib')

    total = 0
    for a, b in pairs:
        total += int(round(difflib.SequenceMatcher(None, a, b).ratio() * 1000))
    matches = 0
    mtotal = 0
    for w, cands in lists:
        found = difflib.get_close_matches(w, cands, n=3, cutoff=0.6)
        matches += len(found)
        mtotal += sum(int(round(difflib.SequenceMatcher(None, w, c).ratio() * 1000))
                      for c in found)
    print('pairs', len(pairs), 'total', total, 'matches', matches, 'mtotal', mtotal)


if __name__ == '__main__':
    main()
