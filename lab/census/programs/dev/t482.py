import statistics
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values: list[int] = [int(tok) for tok in data[1:1 + n]]
    n = len(values)

    if n == 0:
        print("mean: n/a")
        print("median: n/a")
        print("mode: n/a")
        print("pstdev: n/a")
        print("stdev: n/a")
        return

    mean_val = statistics.mean(values)
    median_val = statistics.median(values)

    modes = statistics.multimode(values)
    mode_str = str(modes[0]) if len(modes) == 1 else "multi"

    if n < 2:
        pstdev_str = "n/a"
        stdev_str = "n/a"
    else:
        pstdev_str = f"{statistics.pstdev(values):.3f}"
        stdev_str = f"{statistics.stdev(values):.3f}"

    print(f"mean: {mean_val:.3f}")
    print(f"median: {median_val:.3f}")
    print(f"mode: {mode_str}")
    print(f"pstdev: {pstdev_str}")
    print(f"stdev: {stdev_str}")


if __name__ == "__main__":
    main()
