"""Racy: workers write distinct keys into one shared dict. The keys make the visible result
stable, but the dict's internal storage is written concurrently; print len and one key."""
import threading


def work(k: int, d: dict) -> None:
    d[k] = k * k


def main():
    d = {}
    ts = [threading.Thread(target=work, args=(k, d)) for k in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(d), d.get(0, -1))


main()
