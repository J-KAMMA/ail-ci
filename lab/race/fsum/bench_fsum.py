"""Speedup bench for the opt-in fixed-order float sum: sum of i * 0.001 over N terms."""

N = 200000000


def main():
    acc = 0.0
    for i in par_range(0, N):
        acc += i * 0.001
    print(repr(acc))


if __name__ == "__main__":
    main()
