import sys


def state_at(t: int) -> str:
    """Return the traffic light state at time t.

    Cycle: GREEN for 4 units, YELLOW for 1, RED for 3 (total 8).
    """
    phase = t % 8
    if phase < 4:
        return "GREEN"
    if phase < 5:
        return "YELLOW"
    return "RED"


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    for t in range(n * 3 + 1):
        print(f"{t}: {state_at(t)}")


if __name__ == "__main__":
    main()
