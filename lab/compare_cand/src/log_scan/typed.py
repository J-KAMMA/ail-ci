from ail import read_stdin_bytes, write_stdout_bytes
import sys


class P:

    def __init__(self, ip: int, hh: int, status: int, nb: int, ps: int, pe: int):
        self.ip = ip
        self.hh = hh
        self.status = status
        self.nb = nb
        self.ps = ps
        self.pe = pe


class St:

    def __init__(self, pidx: dict[str, int], pname: list[str], pcount: list[int], pbytes: list[int], ips: set[int], hcount: list[int], hbytes: list[int], scount: list[int], good: int, bad: int, total: int):
        self.pidx = pidx
        self.pname = pname
        self.pcount = pcount
        self.pbytes = pbytes
        self.ips = ips
        self.hcount = hcount
        self.hbytes = hbytes
        self.scount = scount
        self.good = good
        self.bad = bad
        self.total = total


def two(data: bytes, i: int, b: int, lo: int, hi: int) -> int:
    if i + 2 > b:
        return -1
    a0 = data[i]
    a1 = data[i + 1]
    if a0 < 48 or a0 > 57 or a1 < 48 or a1 > 57:
        return -1
    v = (a0 - 48) * 10 + (a1 - 48)
    if v < lo or v > hi:
        return -1
    return v


def year_ok(data: bytes, i: int, b: int) -> bool:
    if i + 4 > b:
        return False
    k = 0
    while k < 4:
        c = data[i + k]
        if c < 48 or c > 57:
            return False
        k += 1
    return True


def month_ok(data: bytes, i: int, b: int) -> bool:
    if i + 3 > b:
        return False
    v = data[i] * 65536 + data[i + 1] * 256 + data[i + 2]
    return (v == 0x4A616E or v == 0x466562 or v == 0x4D6172 or v == 0x417072
            or v == 0x4D6179 or v == 0x4A756E or v == 0x4A756C or v == 0x417567
            or v == 0x536570 or v == 0x4F6374 or v == 0x4E6F76 or v == 0x446563)


def method_ok(data: bytes, a: int, b: int) -> bool:
    n = b - a
    if n == 3:
        c0 = data[a]
        c1 = data[a + 1]
        c2 = data[a + 2]
        if c0 == 71 and c1 == 69 and c2 == 84:
            return True
        if c0 == 80 and c1 == 85 and c2 == 84:
            return True
        return False
    if n == 4:
        return (data[a] == 80 and data[a + 1] == 79 and data[a + 2] == 83
                and data[a + 3] == 84)
    if n == 6:
        return (data[a] == 68 and data[a + 1] == 69 and data[a + 2] == 76
                and data[a + 3] == 69 and data[a + 4] == 84 and data[a + 5] == 69)
    return False


def path_ok(data: bytes, a: int, b: int) -> bool:
    n = b - a
    if n < 1 or n > 64 or data[a] != 47:
        return False
    i = a
    while i < b:
        c = data[i]
        if c >= 65 and c <= 90:
            i += 1
        elif c >= 97 and c <= 122:
            i += 1
        elif c >= 48 and c <= 57:
            i += 1
        elif c == 47 or c == 46 or c == 95 or c == 45:
            i += 1
        else:
            return False
    return True


def parse(data: bytes, a: int, b: int, p: P) -> bool:
    i = a
    ip = 0
    k = 0
    while k < 4:
        if k > 0:
            if i >= b or data[i] != 46:
                return False
            i += 1
        start = i
        v = 0
        while i < b and i - start < 3:
            c = data[i]
            if c < 48 or c > 57:
                break
            v = v * 10 + c - 48
            i += 1
        if i == start or v > 255:
            return False
        ip = ip * 256 + v
        k += 1
    if i + 6 > b:
        return False
    if (data[i] != 32 or data[i + 1] != 45 or data[i + 2] != 32 or data[i + 3] != 45
            or data[i + 4] != 32 or data[i + 5] != 91):
        return False
    i += 6
    if two(data, i, b, 1, 31) < 0:
        return False
    i += 2
    if i >= b or data[i] != 47:
        return False
    i += 1
    if not month_ok(data, i, b):
        return False
    i += 3
    if i >= b or data[i] != 47:
        return False
    i += 1
    if not year_ok(data, i, b):
        return False
    i += 4
    if i >= b or data[i] != 58:
        return False
    i += 1
    hh = two(data, i, b, 0, 23)
    if hh < 0:
        return False
    i += 2
    if i >= b or data[i] != 58:
        return False
    i += 1
    if two(data, i, b, 0, 59) < 0:
        return False
    i += 2
    if i >= b or data[i] != 58:
        return False
    i += 1
    if two(data, i, b, 0, 59) < 0:
        return False
    i += 2
    if i + 7 > b:
        return False
    if (data[i] != 32 or data[i + 1] != 43 or data[i + 2] != 48 or data[i + 3] != 48
            or data[i + 4] != 48 or data[i + 5] != 48 or data[i + 6] != 93):
        return False
    i += 7
    if i >= b or data[i] != 32:
        return False
    i += 1
    if i >= b or data[i] != 34:
        return False
    i += 1
    ms = i
    while i < b and data[i] != 32:
        i += 1
    if i >= b or not method_ok(data, ms, i):
        return False
    i += 1
    ps = i
    while i < b and data[i] != 32:
        i += 1
    if i >= b or not path_ok(data, ps, i):
        return False
    pe = i
    i += 1
    if i + 8 > b:
        return False
    if (data[i] != 72 or data[i + 1] != 84 or data[i + 2] != 84 or data[i + 3] != 80
            or data[i + 4] != 47 or data[i + 5] != 49 or data[i + 6] != 46 or data[i + 7] != 49):
        return False
    i += 8
    if i >= b or data[i] != 34:
        return False
    i += 1
    if i >= b or data[i] != 32:
        return False
    i += 1
    if i + 3 > b:
        return False
    s0 = data[i]
    s1 = data[i + 1]
    s2 = data[i + 2]
    if s0 < 48 or s0 > 57 or s1 < 48 or s1 > 57 or s2 < 48 or s2 > 57:
        return False
    status = (s0 - 48) * 100 + (s1 - 48) * 10 + (s2 - 48)
    if status < 100 or status > 599:
        return False
    i += 3
    if i >= b or data[i] != 32:
        return False
    i += 1
    if i >= b:
        return False
    nb = 0
    if data[i] == 45:
        if i + 1 != b:
            return False
    else:
        if data[i] < 48 or data[i] > 57:
            return False
        while i < b:
            c = data[i]
            if c < 48 or c > 57:
                return False
            nb = nb * 10 + c - 48
            if nb > 1000000000000:
                return False
            i += 1
    p.ip = ip
    p.hh = hh
    p.status = status
    p.nb = nb
    p.ps = ps
    p.pe = pe
    return True


def main() -> int:
    data = read_stdin_bytes(1 << 30)
    n = len(data)
    if n == 0:
        write_stdout_bytes(b'lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n')
        return 0
    st = St({}, [], [], [], set(), [0] * 24, [0] * 24, [0] * 6, 0, 0, 0)
    p = P(0, 0, 0, 0, 0, 0)
    pos = 0
    while pos < n:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        if parse(data, pos, e, p):
            ip = p.ip
            hh = p.hh
            status = p.status
            nb = p.nb
            ps = p.ps
            pe = p.pe
            path = data[ps:pe].decode()
            st.good += 1
            st.total += nb
            cls = status // 100
            if cls >= 2 and cls <= 5:
                st.scount[cls] += 1
            st.hcount[hh] += 1
            st.hbytes[hh] += nb
            pi = st.pidx.get(path, -1)
            if pi < 0:
                pi = len(st.pname)
                st.pidx[path] = pi
                st.pname.append(path)
                st.pcount.append(0)
                st.pbytes.append(0)
            st.pcount[pi] += 1
            st.pbytes[pi] += nb
            st.ips.add(ip)
        else:
            st.bad += 1
        pos = e + 1
    print(f'lines {st.good} bad {st.bad}')
    print(f'status 2xx {st.scount[2]} 3xx {st.scount[3]} 4xx {st.scount[4]} 5xx {st.scount[5]}')
    print(f'bytes {st.total}')
    h = 0
    while h < 24:
        if st.hcount[h] > 0:
            if h < 10:
                print(f'hour 0{h} {st.hcount[h]} {st.hbytes[h]}')
            else:
                print(f'hour {h} {st.hcount[h]} {st.hbytes[h]}')
        h += 1
    pids = [i for i in range(len(st.pname))]
    pids.sort(key=lambda i: (-st.pcount[i], st.pname[i]))
    shown = 0
    for i in pids:
        if shown == 10:
            break
        print(f'path {st.pname[i]} {st.pcount[i]} {st.pbytes[i]}')
        shown += 1
    print(f'ips {len(st.ips)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
