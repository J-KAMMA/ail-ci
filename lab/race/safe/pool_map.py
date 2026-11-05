"""Safe: multiprocessing.Pool.map of a pure int function, closed and joined after the map."""
import multiprocessing


def work(x: int) -> int:
    return x * 3 + 1


def main():
    xs = list(range(40))
    pool = multiprocessing.Pool(4)
    got = pool.map(work, xs)
    pool.close()
    pool.join()
    total = 0
    for v in got:
        total += v
    print(len(got), total, got[0], got[39])


if __name__ == '__main__':
    main()
