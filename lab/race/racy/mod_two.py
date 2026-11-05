"""Racy: workers write out[k % 2], so half of them share each slot. The final contents depend
on the schedule; print only the length and that each slot holds a value someone wrote."""
import threading


def work(k: int, out: list[int]) -> None:
    out[k % 2] = k + 10


def main():
    out = [0] * 2
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out), out[0] >= 10, out[1] >= 10)


main()
