import sys
from heapq import heappush, heappop, heapify
from array import array


def main():
    readline = sys.stdin.buffer.readline

    first = readline().split()
    if not first:
        return
    B = int(first[0])
    S = int(first[1])

    classes = [0] * B
    rates = [0] * B
    for b in range(B):
        c, r = map(int, readline().split())
        classes[b] = c
        rates[b] = r

    SHIFT = 22
    MASK = (1 << SHIFT) - 1
    MASK30 = (1 << 30) - 1

    ids = array('I', [0]) * S
    cargos = array('I', [0]) * S
    ops = array('I', [0]) * S
    sps = bytearray(S)
    keys = [0] * S

    for i in range(S):
        sid, arr, size, carg, p, oper = map(int, readline().split())
        ids[i] = sid
        cargos[i] = carg
        ops[i] = oper
        sps[i] = (size << 4) | p
        keys[i] = (arr << SHIFT) | i

    keys.sort()

    starts = array('q', [0]) * S
    berths = array('H', [0]) * S

    free = [None, [], [], []]
    for b in range(B):
        free[classes[b]].append(b)
    for c in (1, 2, 3):
        heapify(free[c])

    wait = [None, [], [], []]
    counts = [0, 0, 0, 0]

    last_op = [-1] * B
    berth_n = [0] * B
    berth_busy = [0] * B

    depart = []

    ai = 0
    makespan = 0
    total_wait = 0
    max_wait = -1
    max_wait_id = -1

    INF = 1 << 62

    while ai < S or depart:
        if ai < S:
            next_arrival = keys[ai] >> SHIFT
        else:
            next_arrival = INF

        if depart:
            next_departure = depart[0] >> 11
        else:
            next_departure = INF

        t = next_arrival if next_arrival <= next_departure else next_departure

        while depart and (depart[0] >> 11) == t:
            v = heappop(depart)
            b = v & 2047
            heappush(free[classes[b]], b)
            makespan = t

        while ai < S and (keys[ai] >> SHIFT) == t:
            k = keys[ai]
            keys[ai] = 0
            ai += 1

            idx = k & MASK
            arr = k >> SHIFT
            sid = ids[idx]
            sp = sps[idx]
            size = sp >> 4
            p = sp & 15

            wk = (((p << 30) | arr) << 30 | sid) << SHIFT | idx
            heappush(wait[size], wk)
            counts[size] += 1

        if ai >= S:
            keys = None

        while True:
            if counts[1]:
                minsize = 1
            elif counts[2]:
                minsize = 2
            elif counts[3]:
                minsize = 3
            else:
                break

            c = minsize
            while c <= 3 and not free[c]:
                c += 1
            if c > 3:
                break

            b = heappop(free[c])

            best = None
            best_size = 0

            if wait[1]:
                best = wait[1][0]
                best_size = 1
            if c >= 2 and wait[2]:
                kk = wait[2][0]
                if best is None or kk < best:
                    best = kk
                    best_size = 2
            if c >= 3 and wait[3]:
                kk = wait[3][0]
                if best is None or kk < best:
                    best = kk
                    best_size = 3

            wk = heappop(wait[best_size])
            counts[best_size] -= 1

            idx = wk & MASK
            arr = (wk >> (SHIFT + 30)) & MASK30
            sid = ids[idx]
            carg = cargos[idx]
            oper = ops[idx]

            rate = rates[b]
            service = (carg + rate - 1) // rate
            if last_op[b] == oper:
                service += 1
            else:
                service += 4
            last_op[b] = oper

            dep_time = t + service
            heappush(depart, (dep_time << 11) | b)

            berth_n[b] += 1
            berth_busy[b] += service

            starts[idx] = t
            berths[idx] = b

            w = t - arr
            total_wait += w
            if w > max_wait:
                max_wait = w
                max_wait_id = sid
            elif w == max_wait and sid < max_wait_id:
                max_wait_id = sid

    if S == 0:
        max_wait = 0
        max_wait_id = -1

    del wait, free, depart

    if keys is None:
        keys = [0] * S

    for i in range(S):
        keys[i] = (ids[i] << SHIFT) | i

    keys.sort()

    g = 0
    MOD = 1000000007
    for k in keys:
        idx = k & MASK
        g = (g * 1000003 + starts[idx] * 31 + berths[idx]) % MOD

    out = []
    out.append(f"ships {S}")
    out.append(f"makespan {makespan}")
    out.append(f"wait total {total_wait} max {max_wait} ship {max_wait_id}")

    for b in range(B):
        out.append(f"berth {b} ships {berth_n[b]} busy {berth_busy[b]}")

    out.append(f"digest {g}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
