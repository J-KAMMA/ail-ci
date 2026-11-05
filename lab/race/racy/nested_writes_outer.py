"""Racy: an executor inside an executor writes one outer list from several outer tasks. The
outer list's contents depend on the schedule; print only the length and the untouched tail."""
from concurrent.futures import ThreadPoolExecutor

shared = [0] * 8


def inner(j: int) -> int:
    shared[j] = j * j
    return j


def outer(k: int) -> int:
    with ThreadPoolExecutor(max_workers=2) as ex:
        s = 0
        for v in ex.map(inner, range(4)):
            s += v
    return s + k


def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        got = list(ex.map(outer, range(8)))
    print(len(shared), shared[7], len(got))


main()
