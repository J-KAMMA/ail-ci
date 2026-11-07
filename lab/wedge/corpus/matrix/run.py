"""Driver for matrix: dense multiply and reductions over flat int lists."""
import matrix as m

N = 300


def build(n: int, seed: int) -> list[int]:
    out = []
    i = 0
    while i < n * n:
        out.append((i * seed + 3) % 17 - 8)
        i += 1
    return out


def main() -> None:
    a = build(N, 7)
    b = build(N, 11)
    c = m.mat_mul(a, b, N)
    print("n", N)
    print("trace_a", m.trace(a, N))
    print("trace_c", m.trace(c, N))
    rs = m.row_sums(c, N)
    print("rows", len(rs))
    print("row0", rs[0])
    print("max", m.max_element(c))
    print("thresh", m.apply_threshold(c, 1000))
    print("scale", m.scale_vec(a, 3))
    print("negatives", m.count_negative(c))
    idm = m.identity(N)
    print("ident", len(idm), m.trace(idm, N))


main()
