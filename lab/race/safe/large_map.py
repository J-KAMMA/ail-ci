"""Safe: one million independent int results through Pool.map, summed in order afterwards.
The pool is used because ProcessPool chunks the iterable, so a million items do not become one
threaded task per item."""
import multiprocessing


def work(x: int) -> int:
    return (x * 2654435761) % 1000000007


def main():
    xs = list(range(1000000))
    pool = multiprocessing.Pool(8)
    got = pool.map(work, xs)
    pool.close()
    pool.join()
    total = 0
    for v in got:
        total = (total + v) % 1000000007
    print(len(got), total, got[0], got[999999])


if __name__ == '__main__':
    main()
