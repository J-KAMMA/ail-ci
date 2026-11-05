"""Racy: one thread appends to a list while the others index it. The final length is stable
on CPython (all appends happen), but a lock-free build may resize while another reads."""
import threading


def grow(out: list[int]) -> None:
    for i in range(0, 100):
        out.append(i)


def work(k: int, out: list[int]) -> None:
    out[k] = k


def main():
    out = [0] * 8
    ts = [threading.Thread(target=grow, args=(out,))]
    ts += [threading.Thread(target=work, args=(k, out)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out) >= 8, out[0] >= 0)


main()
