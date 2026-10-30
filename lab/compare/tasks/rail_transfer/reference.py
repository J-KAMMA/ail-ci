"""Reference implementation of rail_transfer (see spec.md): reference.py < input

States: (station, line) for every line serving a station, plus one "platform" state per station.
(station, L) -> (other end, L) costs the segment time; (station, L) -> platform costs 0;
platform -> (station, L') costs the station's transfer time and one boarding. The first ride
starts directly in every (S, L). Costs (time, boardings) are packed into one integer
time * 2^32 + boardings, so the heap compares them lexicographically.
"""
import heapq
import sys

SHIFT = 32


def main():
    data = sys.stdin.buffer.read().split()
    pos = 0
    n, m, q = int(data[0]), int(data[1]), int(data[2])
    pos = 3
    xfer = [int(v) for v in data[pos:pos + n]]
    pos += n
    state_of = [dict() for _ in range(n)]     # station -> {line: state id}
    station_of = []
    adj = []
    for _ in range(m):
        u, v, line, t = int(data[pos]), int(data[pos + 1]), int(data[pos + 2]), int(data[pos + 3])
        pos += 4
        su = state_of[u].get(line)
        if su is None:
            su = state_of[u][line] = len(station_of)
            station_of.append(u)
            adj.append([])
        sv = state_of[v].get(line)
        if sv is None:
            sv = state_of[v][line] = len(station_of)
            station_of.append(v)
            adj.append([])
        w = t << SHIFT
        adj[su].append((sv, w))
        adj[sv].append((su, w))
    ns = len(station_of)
    # platform of station u is state ns + u
    for s in range(ns):
        adj[s].append((ns + station_of[s], 0))
    for u in range(n):
        board = (xfer[u] << SHIFT) + 1
        adj.append([(s, board) for s in state_of[u].values()])
    out = []
    INF = 1 << 200
    for _ in range(q):
        s, d = int(data[pos]), int(data[pos + 1])
        pos += 2
        if s == d:
            out.append('0 0')
            continue
        dist = {}
        heap = []
        for st in state_of[s].values():
            dist[st] = 1
            heap.append((1, st))
        heapq.heapify(heap)
        answer = None
        pop = heapq.heappop
        push = heapq.heappush
        get = dist.get
        while heap:
            c, st = pop(heap)
            if c != dist[st]:
                continue
            if st < ns and station_of[st] == d:
                answer = c
                break
            for nxt, w in adj[st]:
                nc = c + w
                if nc < get(nxt, INF):
                    dist[nxt] = nc
                    push(heap, (nc, nxt))
        if answer is None:
            out.append('none')
        else:
            out.append('%d %d' % (answer >> SHIFT, answer & ((1 << SHIFT) - 1)))
    sys.stdout.write(''.join(line + '\n' for line in out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
