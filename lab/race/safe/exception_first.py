"""Safe: two workers raise, and map must report the one the sequential loop reaches first
(x == 5, before x == 9), not whichever thread happens to fail first."""
from concurrent.futures import ThreadPoolExecutor


def work(x: int) -> int:
    if x == 5:
        raise ValueError("bad five")
    if x == 9:
        raise ValueError("bad nine")
    return x * 2


def main():
    xs = list(range(12))
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            got = list(ex.map(work, xs))
        print("ok", len(got))
    except ValueError as e:
        print("error", str(e))


main()
