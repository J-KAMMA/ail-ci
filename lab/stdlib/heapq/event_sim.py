import heapq


def main():
    arrivals = [
        (5, "job-a"),
        (3, "job-b"),
        (8, "job-c"),
        (1, "job-d"),
        (6, "job-e"),
        (2, "job-f"),
    ]
    running = []
    clock = 0
    for duration, name in arrivals:
        clock = clock + 1
        heapq.heappush(running, (clock + duration, name))
        print("start", name, "at", clock)
        while running and running[0][0] <= clock:
            finish, done = heapq.heappop(running)
            print("done", done, "at", finish)
    while running:
        finish, done = heapq.heappop(running)
        print("drain", done, "at", finish)

    recent = []
    for item in [(10, "x"), (4, "y"), (7, "z"), (1, "w")]:
        if len(recent) < 2:
            heapq.heappush(recent, item)
        else:
            print("evict", heapq.heappushpop(recent, item))
    print("recent", sorted(recent, key=lambda row: row[0]))


main()
