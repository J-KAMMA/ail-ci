import sys


def main() -> None:
    data = sys.stdin.read().split()
    lot: set[int] = set()
    for token in data:
        car_id = int(token)
        if car_id in lot:
            lot.remove(car_id)
        else:
            lot.add(car_id)
        print(" ".join(str(c) for c in sorted(lot)))


if __name__ == "__main__":
    main()
