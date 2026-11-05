"""Racy: every worker writes out[0]. The final value depends on the schedule, so this prints
only the length and a fact that holds for every order."""
import threading


def work(k: int, out: list[int]) -> None:
    out[0] = k + 1


def main():
    out = [0] * 8
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out), out[0] >= 0)


main()
