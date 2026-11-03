from ail import read_stdin_bytes, write_stdout_bytes
import sys

class St:

    def __init__(self, slot: dict[str, int], keys: list[str], df: list[int], total: list[int], cur: list[int], touched: list[int], eid: list[int], etf: list[int], start: list[int], stops: set[str]):
        self.slot = slot
        self.keys = keys
        self.df = df
        self.total = total
        self.cur = cur
        self.touched = touched
        self.eid = eid
        self.etf = etf
        self.start = start
        self.stops = stops

def isw(c: int) -> bool:
    return c >= 48 and c <= 57 or (c >= 65 and c <= 90) or (c >= 97 and c <= 122) or (c >= 128)

def add_term(st: St, t: bytearray, alld: bool) -> None:
    tb = bytes(t)
    if alld:
        tb = ('#' + str(len(t))).encode()
    n = len(tb)
    if n < 2:
        return
    key = tb.hex()
    if key in st.stops:
        return
    if n >= 5 and tb[n - 1] == 103 and (tb[n - 2] == 110) and (tb[n - 3] == 105):
        key = tb[0:n - 3].hex()
    elif n >= 4 and tb[n - 1] == 115 and (tb[n - 2] != 115):
        key = tb[0:n - 1].hex()
    id = st.slot.get(key, -1)
    if id < 0:
        id = len(st.keys)
        st.slot[key] = id
        st.keys.append(key)
        st.df.append(0)
        st.total.append(0)
        st.cur.append(0)
    st.total[id] += 1
    if st.cur[id] == 0:
        st.touched.append(id)
    st.cur[id] += 1

def end_doc(st: St) -> None:
    for id in st.touched:
        st.eid.append(id)
        st.etf.append(st.cur[id])
        st.df[id] += 1
        st.cur[id] = 0
    st.touched.clear()
    st.start.append(len(st.eid))

def emit_line(st: St, data: bytes, a: int, b: int) -> None:
    i = a
    while i < b:
        if not isw(data[i]):
            i += 1
            continue
        t = bytearray()
        alld = True
        j = i
        while j < b:
            c = data[j]
            if isw(c):
                if c >= 65 and c <= 90:
                    t.append(c + 32)
                    alld = False
                else:
                    if c < 48 or c > 57:
                        alld = False
                    t.append(c)
                j += 1
            elif (c == 39 or c == 45) and j + 1 < b and isw(data[j + 1]):
                if c == 45:
                    t.append(c)
                    alld = False
                j += 1
            else:
                break
        add_term(st, t, alld)
        i = j

def main() -> int:
    if len(sys.argv) != 2:
        return 1
    ks = sys.argv[1]
    if len(ks) == 0:
        return 1
    k = 0
    for ch in ks.encode():
        if ch < 48 or ch > 57:
            return 1
        k = k * 10 + (ch - 48)
        if k > 100000:
            k = 100000
    if k < 1 or k > 1000:
        return 1
    data = read_stdin_bytes(1 << 40)
    st = St({}, [], [], [], [], [], [], [], [0], set())
    for w in 'an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your'.split():
        st.stops.add(w.encode().hex())
    n = len(data)
    pos = 0
    while pos < n:
        e = data.find(b'\n', pos)
        nxt = 0
        if e < 0:
            e = n
            nxt = n
        else:
            nxt = e + 1
        sep = False
        if e - pos == 2 and data[pos] == 37 and (data[pos + 1] == 37):
            sep = True
        if e - pos == 3 and data[pos] == 37 and (data[pos + 1] == 37) and (data[pos + 2] == 13):
            sep = True
        if sep:
            end_doc(st)
        else:
            emit_line(st, data, pos, e)
        pos = nxt
    end_doc(st)
    nd = len(st.start) - 1
    out = bytearray()
    for d in range(nd):
        lo = st.start[d]
        hi = st.start[d + 1]
        idx: list[int] = []
        sc: list[int] = []
        for q in range(lo, hi):
            idx.append(q - lo)
            tf = st.etf[q]
            sc.append(tf * 1000 * (nd + 1) // (st.df[st.eid[q]] * (tf + 2)))
        idx.sort(key=lambda x: (-sc[x], st.keys[st.eid[lo + x]]))
        out.extend(f'doc {d + 1}:'.encode())
        shown = 0
        for x in idx:
            if shown == k:
                break
            out.append(32)
            out.extend(bytes.fromhex(st.keys[st.eid[lo + x]]))
            out.extend(f'={sc[x]}'.encode())
            shown += 1
        out.append(10)
    ids = [i for i in range(len(st.keys))]
    ids.sort(key=lambda x: (-st.total[x], st.keys[x]))
    out.extend('all:'.encode())
    shown2 = 0
    for x in ids:
        if shown2 == k:
            break
        out.append(32)
        out.extend(bytes.fromhex(st.keys[x]))
        out.extend(f'={st.total[x]}'.encode())
        shown2 += 1
    out.append(10)
    write_stdout_bytes(out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
