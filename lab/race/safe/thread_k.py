"""Safe: the start-all/join-all Thread shape where each worker writes only out[k]."""
import threading


def work(k: int, out: list[int]) -> None:
    out[k] = k * k - 5


def main():
    n = 32
    out = [0] * n
    ts = [threading.Thread(target=work, args=(k, out)) for k in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = 0
    for v in out:
        total += v
    print(len(out), total, out[0], out[31])


main()
