"""Racy: the reduction best = max(best, f(k)) keeps the state in a shared one-element list.
The maximum is order independent here, but the read and write are not one step."""
import threading


def work(k: int, best: list[int]) -> None:
    v = (k * 7) % 13
    if v > best[0]:
        best[0] = v


def main():
    best = [0]
    ts = [threading.Thread(target=work, args=(k, best)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(best), best[0] >= 0)


main()
