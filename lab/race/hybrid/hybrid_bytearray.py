"""Hybrid: the function takes a bytearray. The hybrid has no list/bytearray buffer for this
argument shape, so it must keep CPython's function and still print the same checksum."""
import threading


def checksum(buf: bytearray) -> int:
    s = 0
    for i in range(0, len(buf)):
        s = (s * 31 + buf[i]) % 1000003
    return s


def main():
    buf = bytearray(range(256))
    got = []

    def worker():
        got.append(checksum(buf))

    ts = [threading.Thread(target=worker) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(got), got[0], sorted(got)[0] == sorted(got)[3])


main()
