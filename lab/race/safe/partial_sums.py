"""Safe: each thread keeps a private sum, writes it to out[k], and the join is followed by one
sequential addition of the partial sums."""
import threading


def work(k: int, out: list[int]) -> None:
    s = 0
    for j in range(0, 100):
        s += (k + j) % 17
    out[k] = s


def main():
    n = 8
    out = [0] * n
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(len(out), total, out[0], out[7])


main()
