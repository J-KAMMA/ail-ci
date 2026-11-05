"""Racy: `global total; total += k` is a read-modify-write on one name. The exact total is
schedule dependent even on CPython; print only bounds that hold for every order."""
import threading

total = 0


def work(k: int) -> None:
    global total
    total += k


def main():
    ts = [threading.Thread(target=work, args=(k,)) for k in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(total >= 0, total < 1000)


main()
