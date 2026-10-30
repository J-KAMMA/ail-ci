"""Reference implementation of berth_sim (see spec.md): reference.py < input"""
import heapq
import sys


def main():
    data = sys.stdin.buffer.read().split()
    b, s = int(data[0]), int(data[1])
    pos = 2
    bclass = []
    rate = []
    for _ in range(b):
        bclass.append(int(data[pos]))
        rate.append(int(data[pos + 1]))
        pos += 2
    vals = list(map(int, data[pos:pos + 6 * s]))
    ids = vals[0::6]
    arr = vals[1::6]
    size = vals[2::6]
    cargo = vals[3::6]
    prio = vals[4::6]
    oper = vals[5::6]
    order = sorted(range(s), key=arr.__getitem__)
    start = [0] * s
    where = [0] * s
    free = {1: [], 2: [], 3: []}
    for i in range(b):
        free[bclass[i]].append(i)
    for c in free:
        heapq.heapify(free[c])
    waiting = {1: [], 2: [], 3: []}
    departures = []          # (time, berth)
    last_op = [-1] * b
    served = [0] * b
    busy = [0] * b
    nxt = 0                  # index into order
    makespan = 0
    push, pop = heapq.heappush, heapq.heappop
    while nxt < s or departures:
        t = arr[order[nxt]] if nxt < s else None
        if departures and (t is None or departures[0][0] <= t):
            t = departures[0][0]
        while departures and departures[0][0] == t:
            _, berth = pop(departures)
            push(free[bclass[berth]], berth)
        while nxt < s and arr[order[nxt]] == t:
            i = order[nxt]
            push(waiting[size[i]], (prio[i], arr[i], ids[i], i))
            nxt += 1
        for c in (1, 2, 3):
            fb = free[c]
            while fb:
                best = None
                for z in range(1, c + 1):
                    w = waiting[z]
                    if w and (best is None or w[0] < waiting[best][0]):
                        best = z
                if best is None:
                    break
                berth = pop(fb)
                i = pop(waiting[best])[3]
                dur = -(-cargo[i] // rate[berth]) + (1 if last_op[berth] == oper[i] else 4)
                last_op[berth] = oper[i]
                start[i] = t
                where[i] = berth
                served[berth] += 1
                busy[berth] += dur
                end = t + dur
                if end > makespan:
                    makespan = end
                push(departures, (end, berth))
    out = ['ships %d' % s, 'makespan %d' % makespan]
    if s:
        waits = [start[i] - arr[i] for i in range(s)]
        mx = max(waits)
        who = min(ids[i] for i in range(s) if waits[i] == mx)
        out.append('wait total %d max %d ship %d' % (sum(waits), mx, who))
    else:
        out.append('wait total 0 max 0 ship -1')
    for i in range(b):
        out.append('berth %d ships %d busy %d' % (i, served[i], busy[i]))
    g = 0
    for i in sorted(range(s), key=ids.__getitem__):
        g = (g * 1000003 + start[i] * 31 + where[i]) % 1000000007
    out.append('digest %d' % g)
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
