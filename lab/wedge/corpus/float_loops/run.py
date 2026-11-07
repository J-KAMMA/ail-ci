"""Driver for float_loops: run the numeric kernels over large float lists."""
import float_loops as m

N = 5000000


def main() -> None:
    a = []
    b = []
    for i in range(N):
        a.append((i % 1000) * 0.5 + 0.25)
        b.append((i % 877) * 0.125 + 0.5)
    print("dot", round(m.dot(a, b), 6))
    print("mean", round(m.mean(a), 6))
    print("var", round(m.variance(a), 6))
    print("norm", round(m.norm(a), 6))
    print("maxabs", round(m.max_abs(a), 6))
    print("sqsum", round(m.sq_sum(a), 6))
    print("blend", round(m.blend(a, b, 0.3), 6))
    scaled = m.scale_into(a, 2.5)
    print("scaled_len", len(scaled))
    print("scaled_tail", round(scaled[-1], 6))


main()
