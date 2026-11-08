"""Driver for bitset_bloom: build and probe a filter table."""
import bitset_bloom as m

BITS = 262144
N = 900000
ROUNDS = 3


def main() -> None:
    keys = m.make_hashes(N, 7, 1000003)
    other = m.make_hashes(N, 99, 1000003)
    table = m.bloom_set(keys, BITS)
    hits = 0
    for _r in range(ROUNDS):
        hits += m.bloom_probe(table, keys, BITS)
        hits += m.bloom_probe(table, other, BITS)
    print("bits", BITS)
    print("set", m.popcount(table))
    print("hits", hits)
    print("hits_expected", N * ROUNDS)
    print("xor", m.rotate_xor(keys))
    print("multiples", m.multiples(keys, 7))
    t2 = m.bloom_set(other, BITS)
    print("intersect", m.set_intersect(table, t2))


main()
