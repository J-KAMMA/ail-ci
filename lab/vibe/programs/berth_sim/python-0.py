import sys
import heapq
from array import array


def reorder_array(old, order, mask):
    n = len(order)
    new = array(old.typecode, [0]) * n
    for k in range(n):
        new[k] = old[order[k] & mask]
    return new


def reorder_byte(old, order, mask):
    n = len(order)
    new = bytearray(n)
    for k in range(n):
        new[k] = old[order[k] & mask]
    return new


def main():
    inp = sys.stdin.buffer
    first = inp.readline()
    if not first:
        return

    B, S = map(int, first.split())

    bclass = bytearray(B)
    rate = [0] * B
    free1 = []
    free2 = []
    free3 = []

    for b in range(B):
        c, r = map(int, inp.readline().split())
        bclass[b] = c
        rate[b] = r
        if c == 1:
            free1.append(b)
        elif c == 2:
            free2.append(b)
        else:
            free3.append(b)

    if S == 0:
        out = ["ships 0", "makespan 0", "wait total 0 max 0 ship -1"]
        for b in range(B):
            out.append("berth %d ships 0 busy 0" % b)
        out.append("digest 0")
        sys.stdout.write("\n".join(out) + "\n")
        return

    idx_bits = (S - 1).bit_length()
    if idx_bits == 0:
        idx_bits = 1
    mask = (1 << idx_bits) - 1

    ids = array('I', [0]) * S
    arr = array('Q', [0]) * S
    sizes = bytearray(S)
    cargos = array('I', [0]) * S
    prios = bytearray(S)
    opers = array('I', [0]) * S
    order = [0] * S

    for i in range(S):
        sid, a, z, cargo, p, op = map(int, inp.readline().split())
        ids[i] = sid
        arr[i] = a
        sizes[i] = z
        cargos[i] = cargo
        prios[i] = p
        opers[i] = op
        order[i] = (sid << idx_bits) | i

    # Reorder ships by ascending ID, so index order is ID order.
    order.sort()
    ids = reorder_array(ids, order, mask)
    arr = reorder_array(arr, order, mask)
    sizes = reorder_byte(sizes, order, mask)
    cargos = reorder_array(cargos, order, mask)
    prios = reorder_byte(prios, order, mask)
    opers = reorder_array(opers, order, mask)

    # Sort indices by arrival time.
    for k in range(S):
        order[k] = (arr[k] << idx_bits) | k
    order.sort()

    free_heaps = [None, free1, free2, free3]
    dep_heap = []
    last_op = [-1] * B
    counts = [0] * B
    busy = [0] * B

    w1 = []
    w2 = []
    w3 = []

    heappush = heapq.heappush
    heappop = heapq.heappop

    total_wait = 0
    max_wait = -1
    max_idx = -1
    makespan = 0
    ai = 0
    INF = 1 << 62

    while ai < S or dep_heap:
        if ai < S:
            next_a = order[ai] >> idx_bits
        else:
            next_a = INF

        if dep_heap:
            next_d = dep_heap[0][0]
        else:
            next_d = INF

        t = next_a if next_a < next_d else next_d

        # Departures at t.
        while dep_heap and dep_heap[0][0] == t:
            _, b = heappop(dep_heap)
            c = bclass[b]
            if c == 1:
                heappush(free1, b)
            elif c == 2:
                heappush(free2, b)
            else:
                heappush(free3, b)

        # Arrivals at t.
        while ai < S:
            val = order[ai]
            a = val >> idx_bits
            if a != t:
                break

            idx = val & mask
            order[ai] = 0
            ai += 1

            z = sizes[idx]
            key = (((prios[idx] << 30) | a) << idx_bits) | idx

            if z == 1:
                heappush(w1, key)
            elif z == 2:
                heappush(w2, key)
            else:
                heappush(w3, key)

        # Assign free berths in class order.
        for c in (1, 2, 3):
            fh = free_heaps[c]

            while fh:
                if c == 1:
                    if not w1:
                        break
                    key = w1[0]
                    src = 1
                elif c == 2:
                    if w1:
                        if w2 and w2[0] < w1[0]:
                            key = w2[0]
                            src = 2
                        else:
                            key = w1[0]
                            src = 1
                    else:
                        if not w2:
                            break
                        key = w2[0]
                        src = 2
                else:
                    if w1:
                        key = w1[0]
                        src = 1
                    else:
                        key = None

                    if w2 and (key is None or w2[0] < key):
                        key = w2[0]
                        src = 2
                    if w3 and (key is None or w3[0] < key):
                        key = w3[0]
                        src = 3

                    if key is None:
                        break

                b = heappop(fh)

                if src == 1:
                    heappop(w1)
                elif src == 2:
                    heappop(w2)
                else:
                    heappop(w3)

                idx = key & mask
                cargo = cargos[idx]
                op = opers[idx]
                r = rate[b]

                service = (cargo + r - 1) // r
                if last_op[b] == op:
                    service += 1
                else:
                    service += 4
                last_op[b] = op

                wait = t - arr[idx]
                total_wait += wait
                if wait > max_wait or (wait == max_wait and idx < max_idx):
                    max_wait = wait
                    max_idx = idx

                arr[idx] = t
                opers[idx] = b

                counts[b] += 1
                busy[b] += service

                dep = t + service
                heappush(dep_heap, (dep, b))
                if dep > makespan:
                    makespan = dep

    g = 0
    for i in range(S):
        g = (g * 1000003 + arr[i] * 31 + opers[i]) % 1000000007

    max_ship = ids[max_idx] if max_idx >= 0 else -1

    out = []
    out.append("ships %d" % S)
    out.append("makespan %d" % makespan)
    out.append("wait total %d max %d ship %d" % (total_wait, max_wait, max_ship))
    for b in range(B):
        out.append("berth %d ships %d busy %d" % (b, counts[b], busy[b]))
    out.append("digest %d" % g)

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
