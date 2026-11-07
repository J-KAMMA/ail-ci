import sys
import heapq


def main():
    readline = sys.stdin.readline

    line = readline()
    if not line:
        return

    parts = line.split()
    B = int(parts[0])
    S = int(parts[1])

    classes = [0] * B
    rates = [0] * B
    for i in range(B):
        parts = readline().split()
        classes[i] = int(parts[0])
        rates[i] = int(parts[1])

    ships = []
    append_ship = ships.append
    for _ in range(S):
        parts = readline().split()
        sid = int(parts[0])
        arr = int(parts[1])
        size = int(parts[2])
        cargo = int(parts[3])
        prio = int(parts[4])
        op = int(parts[5])
        append_ship((arr, sid, size, cargo, prio, op))

    ships.sort()

    free1 = []
    free2 = []
    free3 = []
    for b in range(B):
        c = classes[b]
        if c == 1:
            free1.append(b)
        elif c == 2:
            free2.append(b)
        else:
            free3.append(b)

    wait1 = []
    wait2 = []
    wait3 = []
    departures = []
    last_op = [-1] * B
    served = [0] * B
    busy = [0] * B
    results = []

    INF = 1 << 62
    i = 0
    total_wait = 0
    max_wait = -1
    max_id = -1
    makespan = 0

    while True:
        next_arrival = ships[i][0] if i < S else INF
        next_departure = departures[0][0] if departures else INF

        if next_arrival == INF and next_departure == INF:
            break

        if next_arrival <= next_departure:
            t = next_arrival
        else:
            t = next_departure

        while departures and departures[0][0] == t:
            entry = heapq.heappop(departures)
            b = entry[1]
            c = classes[b]
            if c == 1:
                heapq.heappush(free1, b)
            elif c == 2:
                heapq.heappush(free2, b)
            else:
                heapq.heappush(free3, b)
            makespan = t

        while i < S and ships[i][0] == t:
            ship = ships[i]
            heapq.heappush(wait3 if ship[2] == 3 else (wait2 if ship[2] == 2 else wait1),
                           (ship[4], ship[0], ship[1], ship[3], ship[5]))
            i += 1

        for c in (1, 2, 3):
            if c == 1:
                fh = free1
            elif c == 2:
                fh = free2
            else:
                fh = free3

            while fh:
                best = None
                best_size = 0

                if wait1:
                    best = wait1[0]
                    best_size = 1

                if c >= 2 and wait2:
                    top = wait2[0]
                    if best is None or top < best:
                        best = top
                        best_size = 2

                if c >= 3 and wait3:
                    top = wait3[0]
                    if best is None or top < best:
                        best = top
                        best_size = 3

                if best is None:
                    break

                b = heapq.heappop(fh)
                if best_size == 1:
                    entry = heapq.heappop(wait1)
                elif best_size == 2:
                    entry = heapq.heappop(wait2)
                else:
                    entry = heapq.heappop(wait3)

                prio = entry[0]
                arr = entry[1]
                sid = entry[2]
                cargo = entry[3]
                op = entry[4]

                wt = t - arr
                total_wait += wt
                if wt > max_wait or (wt == max_wait and sid < max_id):
                    max_wait = wt
                    max_id = sid

                if last_op[b] == op:
                    setup = 1
                else:
                    setup = 4
                last_op[b] = op

                rate = rates[b]
                service = (cargo + rate - 1) // rate + setup

                served[b] += 1
                busy[b] += service
                results.append((sid, t, b))
                heapq.heappush(departures, (t + service, b))

    if max_wait < 0:
        max_wait = 0
        max_id = -1

    results.sort()
    digest = 0
    for r in results:
        digest = (digest * 1000003 + r[1] * 31 + r[2]) % 1000000007

    out = []
    out.append("ships %d\n" % S)
    out.append("makespan %d\n" % makespan)
    out.append("wait total %d max %d ship %d\n" % (total_wait, max_wait, max_id))
    for b in range(B):
        out.append("berth %d ships %d busy %d\n" % (b, served[b], busy[b]))
    out.append("digest %d\n" % digest)

    sys.stdout.write("".join(out))


main()
