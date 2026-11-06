import sys
import heapq
from array import array


def main():
    read = sys.stdin.buffer.readline
    first = read().split()
    if not first:
        return

    B = int(first[0])
    S = int(first[1])

    bcls = [0] * B
    brate = [0] * B
    for i in range(B):
        c, r = map(int, read().split())
        bcls[i] = c
        brate[i] = r

    id_arr = array('I')
    arr_arr = array('I')
    size_arr = bytearray()
    cargo_arr = array('I')
    prio_arr = bytearray()
    op_arr = array('I')

    ia = id_arr.append
    aa = arr_arr.append
    za = size_arr.append
    ca = cargo_arr.append
    pa = prio_arr.append
    oa = op_arr.append

    for _ in range(S):
        sid, ar, sz, cg, pr, op = map(int, read().split())
        ia(sid)
        aa(ar)
        za(sz)
        ca(cg)
        pa(pr)
        oa(op)

    start = array('q', [0]) * S
    berth = array('h', [-1]) * S

    MASK = (1 << 22) - 1

    order = [(arr_arr[i] << 22) | i for i in range(S)]
    order.sort()
    order = array('Q', order)

    wait_heaps = [[], [], [], []]
    free_heaps = [[], [], [], []]
    for b in range(B):
        free_heaps[bcls[b]].append(b)

    last_op = [-1] * B
    busy = [0] * B
    served = [0] * B
    dep_heap = []

    heappush = heapq.heappush
    heappop = heapq.heappop

    i_arr = 0
    waiting_count = 0
    free_count = B
    makespan = 0
    total_wait = 0
    max_wait = 0
    max_wait_id = -1

    while i_arr < S or dep_heap:
        if i_arr < S:
            na = order[i_arr] >> 22
        else:
            na = -1

        if dep_heap:
            nd = dep_heap[0][0]
        else:
            nd = -1

        if na != -1 and (nd == -1 or na <= nd):
            t = na
        else:
            t = nd

        while dep_heap and dep_heap[0][0] == t:
            _, b = heappop(dep_heap)
            heappush(free_heaps[bcls[b]], b)
            free_count += 1
            makespan = t

        while i_arr < S:
            ov = order[i_arr]
            if (ov >> 22) != t:
                break

            idx = ov & MASK
            z = size_arr[idx]
            ar = arr_arr[idx]
            key = (((prio_arr[idx] << 30) | ar) << 30 | id_arr[idx]) << 22 | idx
            heappush(wait_heaps[z], key)
            waiting_count += 1
            i_arr += 1

        if i_arr == S:
            order = None

        if waiting_count and free_count:
            for c in (1, 2, 3):
                fh = free_heaps[c]
                if not fh:
                    continue

                while fh:
                    best_key = -1
                    best_z = 0

                    for z in range(1, c + 1):
                        h = wait_heaps[z]
                        if h:
                            k = h[0]
                            if best_key == -1 or k < best_key:
                                best_key = k
                                best_z = z

                    if best_key == -1:
                        break

                    best_key = heappop(wait_heaps[best_z])
                    waiting_count -= 1

                    b = heappop(fh)
                    free_count -= 1

                    idx = best_key & MASK
                    op = op_arr[idx]

                    if last_op[b] == op:
                        setup = 1
                    else:
                        setup = 4
                        last_op[b] = op

                    cargo = cargo_arr[idx]
                    rate = brate[b]
                    service = (cargo + rate - 1) // rate + setup
                    dep = t + service
                    heappush(dep_heap, (dep, b))

                    start[idx] = t
                    berth[idx] = b
                    busy[b] += service
                    served[b] += 1

                    w = t - arr_arr[idx]
                    total_wait += w
                    sid = id_arr[idx]

                    if w > max_wait or (
                        w == max_wait and (max_wait_id == -1 or sid < max_wait_id)
                    ):
                        max_wait = w
                        max_wait_id = sid

                if waiting_count == 0:
                    break

    del arr_arr, size_arr, cargo_arr, prio_arr, op_arr
    del wait_heaps, free_heaps, dep_heap, last_op, bcls, brate
    if order is not None:
        del order

    id_order = [(id_arr[i] << 22) | i for i in range(S)]
    id_order.sort()

    g = 0
    for key in id_order:
        i = key & MASK
        g = (g * 1000003 + start[i] * 31 + berth[i]) % 1000000007

    out = []
    out.append("ships " + str(S))
    out.append("makespan " + str(makespan))
    out.append(
        "wait total "
        + str(total_wait)
        + " max "
        + str(max_wait)
        + " ship "
        + str(max_wait_id)
    )

    for b in range(B):
        out.append(
            "berth "
            + str(b)
            + " ships "
            + str(served[b])
            + " busy "
            + str(busy[b])
        )

    out.append("digest " + str(g))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
