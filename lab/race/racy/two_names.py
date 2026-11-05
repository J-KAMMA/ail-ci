"""Racy: a = out is the same list under two names. A worker writes out[k] and reads
a[(k + 1) % 8], which another worker may be writing. Print only the length."""
import threading


def work(k: int, out: list[int], a: list[int]) -> None:
    out[k] = k + 1
    out[k] = out[k] + a[(k + 1) % 8]


def main():
    out = [0] * 8
    a = out
    ts = [threading.Thread(target=work, args=(k, out, a)) for k in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(out))


main()
