import sys
import heapq


def main():
    line = sys.stdin.readline()
    if not line:
        return

    first = line.split()
    B = int(first[0])
    S = int(first[1])

    berth_class = [0] * B
    berth_rate = [0] * B
    previous_operator = [-1] * B
    served_count = [0] * B
    busy_total = [0] * B

    free1 = []
    free2 = []
    free3 = []

    for b in range(B):
        parts = sys.stdin.readline().split()
        c = int(parts[0])
        r = int(parts[1])
        berth_class[b] = c
        berth_rate[b] = r
        if c == 1:
            free1.append(b)
        elif c == 2:
            free2.append(b)
        else:
            free3.append(b)

    ships = []

    for _ in range(S):
        parts = sys.stdin.readline().split()
        ship_id = int(parts[0])
        arrival = int(parts[1])
        size = int(parts[2])
        cargo = int(parts[3])
        priority = int(parts[4])
        operator = int(parts[5])
        ships.append((arrival, ship_id, size, cargo, priority, operator))

    ships.sort()

    wait1 = []
    wait2 = []
    wait3 = []
    departures = []
    final = []

    A = 1000000001
    N = S + 1
    INF = 1 << 62

    idx = 0
    total_wait = 0
    max_wait = -1
    max_wait_id = -1
    makespan = 0

    while idx < S or departures:
        if idx < S:
            t = ships[idx][0]
        else:
            t = INF

        if departures:
            dtime = departures[0] // B
            if dtime < t:
                t = dtime

        while departures and departures[0] // B == t:
            dk = heapq.heappop(departures)
            b = dk % B
            c = berth_class[b]
            if c == 1:
                heapq.heappush(free1, b)
            elif c == 2:
                heapq.heappush(free2, b)
            else:
                heapq.heappush(free3, b)

        while idx < S and ships[idx][0] == t:
            rec = ships[idx]
            base = rec[4] * A + rec[0]
            key = base * N + idx
            size = rec[2]
            if size == 1:
                heapq.heappush(wait1, key)
            elif size == 2:
                heapq.heappush(wait2, key)
            else:
                heapq.heappush(wait3, key)
            idx += 1

        for cls in (1, 2, 3):
            if cls == 1:
                berths = free1
            elif cls == 2:
                berths = free2
            else:
                berths = free3

            while berths:
                best_key = INF
                best_size = 0

                if wait1 and wait1[0] < best_key:
                    best_key = wait1[0]
                    best_size = 1

                if cls >= 2 and wait2:
                    v = wait2[0]
                    if v < best_key:
                        best_key = v
                        best_size = 2

                if cls >= 3 and wait3:
                    v = wait3[0]
                    if v < best_key:
                        best_key = v
                        best_size = 3

                if best_size == 0:
                    break

                if best_size == 1:
                    key = heapq.heappop(wait1)
                elif best_size == 2:
                    key = heapq.heappop(wait2)
                else:
                    key = heapq.heappop(wait3)

                b = heapq.heappop(berths)
                ship_index = key % N
                rec = ships[ship_index]

                arrival = rec[0]
                ship_id = rec[1]
                cargo = rec[3]
                operator = rec[5]

                rate = berth_rate[b]
                service = (cargo + rate - 1) // rate

                if previous_operator[b] == operator:
                    service += 1
                else:
                    service += 4

                previous_operator[b] = operator
                departure = t + service

                served_count[b] += 1
                busy_total[b] += service

                heapq.heappush(departures, departure * B + b)
                final.append((ship_id, t, b))

                if departure > makespan:
                    makespan = departure

                wait = t - arrival
                total_wait += wait

                if wait > max_wait:
                    max_wait = wait
                    max_wait_id = ship_id
                elif wait == max_wait and ship_id < max_wait_id:
                    max_wait_id = ship_id

    if S == 0:
        max_wait = 0
        max_wait_id = -1

    final.sort()

    digest = 0
    for rec in final:
        digest = (digest * 1000003 + rec[1] * 31 + rec[2]) % 1000000007

    out = []
    out.append("ships " + str(S))
    out.append("makespan " + str(makespan))
    out.append(
        "wait total " + str(total_wait)
        + " max " + str(max_wait)
        + " ship " + str(max_wait_id)
    )

    for b in range(B):
        out.append(
            "berth " + str(b)
            + " ships " + str(served_count[b])
            + " busy " + str(busy_total[b])
        )

    out.append("digest " + str(digest))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
