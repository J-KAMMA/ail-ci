"""Hybrid: one CPython thread appends to a list while another calls the accelerated total().

The accelerated native call releases the GIL, so this is the hybrid race candidate named in the
job. Print only the final length, that exactly one sum was captured, and that the sum is non-negative
(always true for prefixes of 0..1999), so CPython and the hybrid agree whatever the schedule.
"""
import threading

import hybrid_list_append


def grow(xs: list[int]) -> None:
    for i in range(1000, 2000):
        xs.append(i)


def read(xs: list[int], seen: list[int]) -> None:
    seen.append(hybrid_list_append.total(xs))


def main():
    xs = list(range(1000))
    seen = []
    grower = threading.Thread(target=grow, args=(xs,))
    reader = threading.Thread(target=read, args=(xs, seen))
    grower.start()
    reader.start()
    grower.join()
    reader.join()
    print(len(xs), len(seen), seen[0] >= 0)


main()
