"""Safe since D3 (2026-11-06): every worker appends to one shared list. The typed parallel build
gives each block its own buffer and joins them in iteration order, so the length equals the
sequential loop's; the general path's lock gives the same length."""
import threading


def work(k: int, xs: list[int]) -> None:
    xs.append(k * k)


def main():
    xs = []
    ts = [threading.Thread(target=work, args=(k, xs)) for k in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(xs))


main()
