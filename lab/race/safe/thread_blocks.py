"""Safe: each worker owns a block out[k * 8 + j] with j from an inner range(0, 8)."""
import threading


def work(k: int, out: list[int]) -> None:
    for j in range(0, 8):
        out[k * 8 + j] = k + j * 3


def main():
    n = 5
    out = [0] * (n * 8)
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(len(out), total, out[0], out[n * 8 - 1])


main()
