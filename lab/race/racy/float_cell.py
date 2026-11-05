"""Racy: each worker adds a float into the shared cell acc[0]. Floating-point addition is not
associative, so the sum depends on the order; print only that it stayed finite and positive."""
import threading


def work(k: int, acc: list[float]) -> None:
    acc[0] = acc[0] + float(k) / 3.0


def main():
    acc = [0.0]
    ts = [threading.Thread(target=work, args=(k, acc)) for k in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(acc), acc[0] >= 0.0)


main()
