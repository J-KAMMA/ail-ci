"""Hybrid: a CPython thread appends to a list while another calls the accelerated total(),
which reads that list. The hybrid releases the GIL around the native read. Print only the
final length and that every captured sum was finite."""
import threading


def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s


def main():
    xs = list(range(1000))
    seen = []

    def grow():
        for i in range(1000, 2000):
            xs.append(i)

    def read():
        seen.append(total(xs))

    a = threading.Thread(target=grow)
    b = threading.Thread(target=read)
    a.start()
    b.start()
    a.join()
    b.join()
    print(len(xs), len(seen), seen[0] >= 0)


main()
