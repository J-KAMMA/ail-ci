"""Tiny body over ten million items: the per-item arithmetic is a couple of instructions."""
import multiprocessing

N = 10000000


def work(x: int) -> int:
    return (x * 13 + 7) & 1023


def main():
    pool = multiprocessing.Pool(4)
    res = pool.map(work, range(N))
    pool.close()
    pool.join()
    total = 0
    for v in res:
        total += v
    print(len(res), total, res[0], res[N - 1])


if __name__ == "__main__":
    main()
