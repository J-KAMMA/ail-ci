"""Racy: tasks made by executor.submit write a shared list at k % 4. Which value each slot
ends with depends on the schedule; print only the length of the list."""
from concurrent.futures import ThreadPoolExecutor


def work(k: int, out: list[int]) -> None:
    out[k % 4] = k


def main():
    out = [0] * 4
    with ThreadPoolExecutor(max_workers=4) as ex:
        fus = [ex.submit(work, k, out) for k in range(8)]
        for f in fus:
            f.result()
    print(len(out))


main()
