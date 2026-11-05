"""Racy: the same list is passed twice in args=(k, out, out), so the read-only-looking second
argument aliases the list each worker writes. The result depends on the schedule; print len."""
import threading


def work(k: int, out: list[int], other: list[int]) -> None:
    out[k] = k
    out[k] = out[k] + other[(k * 7 + 1) % 8]


def main():
    out = [0] * 8
    ts = [threading.Thread(target=work, args=(k, out, out)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out))


main()
