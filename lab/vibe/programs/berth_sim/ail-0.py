import sys
import heapq


def main():
    line = sys.stdin.readline()
    if not line:
        return

    parts = line.split()
    B = int(parts[0])
    S = int(parts[1])

    cls: list[int] = [0] * B
    rate: list[int] = [0] * B

    for b in range(B):
        p = sys.stdin.readline().split()
        cls[b] = int(p[0])
        rate[b] = int(p[1])

    records: list[tuple[int, int, int, int, int, int]] = []
    append_record = records.append

    for _ in range(S):
        p = sys.stdin.readline().split()
        sid = int(p[0])
        arr = int(p[1])
        size = int(p[2])
        cargo = int(p[3])
        pri = int(p[4])
        op = int(p[5])
        append_record((arr, pri, sid, size, cargo, op))

    records.sort()

    last_op: list[int] = [-1] * B
    count: list[int] = [0] * B
    busy: list[int] = [0] * B

    wait: list[list[tuple[int, int, int, int, int, int]]] = [[], [], [], []]
    free: list[list[int]] = [[], [], [], []]

    for b in range(B):
        free[cls[b]].append(b)

    for c in (1, 2, 3):
        heapq.heapify(free[c])

    departures: list[tuple[int, int]] = []
    results: list[tuple[int, int]] = []

    idx = 0
    n = S
    makespan = 0
    wait_total = 0
    max_wait = 0
    max_id = -1

    while idx < n or departures:
        if departures:
            t = departures[0][0]
            if idx < n:
                a = records[idx][0]
                if a < t:
                    t = a
        else:
            t = records[idx][0]

        while departures and departures[0][0] == t:
            _, db = heapq.heappop(departures)
            heapq.heappush(free[cls[db]], db)

        while idx < n and records[idx][0] == t:
            arr, pri, sid, size, cargo, op = records[idx]
            idx += 1
            heapq.heappush(wait[size], (pri, arr, sid, size, cargo, op))

        for c in (1, 2, 3):
            fh = free[c]
            if not fh:
                continue

            while fh:
                if c == 1:
                    if not wait[1]:
                        break
                    rec = heapq.heappop(wait[1])

                elif c == 2:
                    if wait[1]:
                        if wait[2]:
                            if wait[1][0] <= wait[2][0]:
                                rec = heapq.heappop(wait[1])
                            else:
                                rec = heapq.heappop(wait[2])
                        else:
                            rec = heapq.heappop(wait[1])
                    elif wait[2]:
                        rec = heapq.heappop(wait[2])
                    else:
                        break

                else:
                    if wait[1]:
                        src = 1
                        best = wait[1][0]
                    elif wait[2]:
                        src = 2
                        best = wait[2][0]
                    elif wait[3]:
                        src = 3
                        best = wait[3][0]
                    else:
                        break

                    if wait[2] and wait[2][0] < best:
                        best = wait[2][0]
                        src = 2
                    if wait[3] and wait[3][0] < best:
                        best = wait[3][0]
                        src = 3

                    if src == 1:
                        rec = heapq.heappop(wait[1])
                    elif src == 2:
                        rec = heapq.heappop(wait[2])
                    else:
                        rec = heapq.heappop(wait[3])

                b = heapq.heappop(fh)
                pri, arr, sid, size, cargo, op = rec
                r = rate[b]
                setup = 1 if last_op[b] == op else 4
                service = (cargo + r - 1) // r + setup

                start = t
                finish = start + service

                heapq.heappush(departures, (finish, b))
                last_op[b] = op
                count[b] += 1
                busy[b] += service

                if finish > makespan:
                    makespan = finish

                w = start - arr
                wait_total += w

                if w > max_wait or (w == max_wait and (max_id == -1 or sid < max_id)):
                    max_wait = w
                    max_id = sid

                results.append((sid, start * 31 + b))

    results.sort()

    digest = 0
    for sid, value in results:
        digest = (digest * 1000003 + value) % 1000000007

    out: list[str] = []
    out.append("ships " + str(S))
    out.append("makespan " + str(makespan))
    out.append(
        "wait total "
        + str(wait_total)
        + " max "
        + str(max_wait)
        + " ship "
        + str(max_id)
    )

    for b in range(B):
        out.append(
            "berth "
            + str(b)
            + " ships "
            + str(count[b])
            + " busy "
            + str(busy[b])
        )

    out.append("digest " + str(digest))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
