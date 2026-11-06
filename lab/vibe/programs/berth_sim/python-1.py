import sys
import heapq


def main():
    read = sys.stdin.buffer.readline
    first = read().split()
    if not first:
        return

    B = int(first[0])
    S = int(first[1])

    berth_class = [0] * B
    rate = [0] * B
    free = [[], [], [], []]

    for i in range(B):
        c, r = map(int, read().split())
        berth_class[i] = c
        rate[i] = r
        free[c].append(i)

    for c in (1, 2, 3):
        heapq.heapify(free[c])

    M20 = (1 << 20) - 1
    M30 = (1 << 30) - 1
    M60 = (1 << 60) - 1

    ships = []
    add_ship = ships.append
    for _ in range(S):
        sid, arr, size, cargo, prio, op = map(int, read().split())
        add_ship((arr << 76) | (prio << 72) | (sid << 42) | (size << 40) | (cargo << 20) | op)

    ships.sort()

    waiting = [[], [], [], []]
    dep_heap = []

    last_op = [-1] * B
    busy = [0] * B
    cnt = [0] * B
    assignments = []

    total_wait = 0
    max_wait = -1
    max_id = -1
    makespan = 0

    ptr = 0
    n = S
    heappush = heapq.heappush
    heappop = heapq.heappop
    INF = 1 << 62

    while ptr < n or dep_heap:
        if ptr < n:
            next_arr = ships[ptr] >> 76
        else:
            next_arr = INF

        if dep_heap:
            next_dep = dep_heap[0][0]
        else:
            next_dep = INF

        t = next_arr if next_arr < next_dep else next_dep

        if dep_heap and dep_heap[0][0] == t:
            makespan = t
            while dep_heap and dep_heap[0][0] == t:
                _, b = heappop(dep_heap)
                heappush(free[berth_class[b]], b)

        while ptr < n and (ships[ptr] >> 76) == t:
            p = ships[ptr]
            ships[ptr] = 0

            op = p & M20
            cargo = (p >> 20) & M20
            size = (p >> 40) & 3
            sid = (p >> 42) & M30
            prio = (p >> 72) & 15

            heappush(
                waiting[size],
                (prio << 100) | (t << 70) | (sid << 40) | (cargo << 20) | op,
            )
            ptr += 1

        for c in (1, 2, 3):
            fh = free[c]
            if not fh:
                continue

            while fh:
                best = None
                best_size = 0

                w1 = waiting[1]
                if w1:
                    best = w1[0]
                    best_size = 1

                if c >= 2:
                    w2 = waiting[2]
                    if w2:
                        it = w2[0]
                        if best is None or it < best:
                            best = it
                            best_size = 2

                if c >= 3:
                    w3 = waiting[3]
                    if w3:
                        it = w3[0]
                        if best is None or it < best:
                            best = it
                            best_size = 3

                if best is None:
                    break

                b = heappop(fh)
                heappop(waiting[best_size])

                op = best & M20
                cargo = (best >> 20) & M20
                sid = (best >> 40) & M30
                arr = (best >> 70) & M30

                r = rate[b]
                service = (cargo + r - 1) // r

                if last_op[b] == op:
                    service += 1
                else:
                    service += 4

                last_op[b] = op
                busy[b] += service
                cnt[b] += 1
                heappush(dep_heap, (t + service, b))

                wait = t - arr
                total_wait += wait

                if wait > max_wait or (wait == max_wait and sid < max_id):
                    max_wait = wait
                    max_id = sid

                assignments.append((sid << 60) | (t * 31 + b))

    if max_wait < 0:
        max_wait = 0
        max_id = -1

    out = [
        "ships " + str(S),
        "makespan " + str(makespan),
        "wait total " + str(total_wait) + " max " + str(max_wait) + " ship " + str(max_id),
    ]

    for b in range(B):
        out.append("berth " + str(b) + " ships " + str(cnt[b]) + " busy " + str(busy[b]))

    assignments.sort()
    g = 0
    for p in assignments:
        g = (g * 1000003 + (p & M60)) % 1000000007

    out.append("digest " + str(g))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
