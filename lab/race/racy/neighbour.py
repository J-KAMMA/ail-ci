"""Racy: a worker writes the neighbour out[k + 1], not out[k]. The write is outside the
ownership shape par_range accepts; the docstring is the only schedule-independent claim."""
import threading


def work(k: int, out: list[int]) -> None:
    out[k + 1] = k * 3


def main():
    n = 7
    out = [0] * (n + 1)
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out), out[0], out[n] >= 0)


main()
