"""Driver for rolling_stats: window sums and runs over generated samples."""
import rolling_stats as m

N = 3000000
W = 128
ROUNDS = 2


def main() -> None:
    xs = m.make_samples(N, 12345)
    total = 0
    runs = 0
    over = 0
    for _r in range(ROUNDS):
        sums = m.window_sums(xs, W)
        total += sums[-1]
        runs += m.longest_run(xs, 0)
        runs += m.rising_streak(xs)
        over += m.count_over(xs, 900)
    print("n", len(xs))
    print("windows", len(m.window_sums(xs, W)))
    print("total", m.total(xs))
    print("moment", m.second_moment(xs))
    print("mean_scaled", m.mean_scaled(xs, 3))
    print("runs", runs)
    print("over", over)
    print("acc", total)


main()
