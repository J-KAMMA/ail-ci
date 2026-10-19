import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    # The quantum is read for input compatibility but is not used by SJF.
    _quantum = int(data[1]) if len(data) > 1 else 0

    processes: list[tuple[str, int]] = []
    idx = 2
    for _ in range(n):
        name = data[idx]
        burst = int(data[idx + 1])
        processes.append((name, burst))
        idx += 2

    # Non-preemptive SJF with all arrivals at time 0.
    # sorted() is stable, so ties keep their input order.
    order = sorted(processes, key=lambda p: p[1])

    waiting: dict[str, int] = {}
    elapsed = 0
    for name, burst in order:
        waiting[name] = elapsed
        elapsed += burst

    total_wait = sum(waiting.values())
    average = total_wait / len(order) if order else 0.0

    print("Order: " + " ".join(name for name, _ in order))
    for name, _ in order:
        print(f"{name} waiting time: {waiting[name]}")
    print(f"Average waiting time: {average:.2f}")


if __name__ == "__main__":
    main()
