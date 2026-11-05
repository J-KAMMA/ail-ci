"""Racy: every worker appends to one shared list. CPython's GIL keeps each append whole, so it
prints the length below; on a lock-free build the same statement is a data race."""
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
