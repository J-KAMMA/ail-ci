"""Linear-ramp parallel map: item x does x rounds of integer mixing."""
import multiprocessing

N = 20000


def work(x: int) -> int:
    v = x * 3 + 1
    k = 0
    while k < x:
        v = (v * 5 + 7) & 0x3FFFFFFF
        k += 1
    return v


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
