from ail import read_bytes
import sys

class State:

    def __init__(self, vidx: dict[str, int], vcode: list[str], vcap: list[int], vnev: list[int], vtix: list[int], vrev: list[int], evidx: dict[int, int], evnum: list[int], evven: list[int], evprice: list[int], evsold: list[int], seats: set[str], nrec: int, ns: int, nr: int, rev: int):
        self.vidx = vidx
        self.vcode = vcode
        self.vcap = vcap
        self.vnev = vnev
        self.vtix = vtix
        self.vrev = vrev
        self.evidx = evidx
        self.evnum = evnum
        self.evven = evven
        self.evprice = evprice
        self.evsold = evsold
        self.seats = seats
        self.nrec = nrec
        self.ns = ns
        self.nr = nr
        self.rev = rev

def isd(c: int) -> bool:
    return c >= 48 and c <= 57

def isup(c: int) -> bool:
    return c >= 65 and c <= 90

def islow(c: int) -> bool:
    return c >= 97 and c <= 122

def digits(f: bytes, lo: int, hi: int) -> bool:
    n = len(f)
    if n < lo or n > hi:
        return False
    for i in range(n):
        if not isd(f[i]):
            return False
    return True

def s_code(f: bytes) -> bool:
    if len(f) != 3:
        return False
    for i in range(3):
        if not isup(f[i]):
            return False
    return True

def s_name(f: bytes) -> bool:
    n = len(f)
    if n < 1 or n > 40:
        return False
    for i in range(n):
        if f[i] < 32 or f[i] > 126:
            return False
    if f[0] == 32 or f[n - 1] == 32:
        return False
    return True

def s_date(f: bytes) -> bool:
    if len(f) != 10:
        return False
    for i in range(10):
        if i == 4 or i == 7:
            if f[i] != 45:
                return False
        elif not isd(f[i]):
            return False
    return True

def s_time(f: bytes) -> bool:
    if len(f) != 5:
        return False
    for i in range(5):
        if i == 2:
            if f[i] != 58:
                return False
        elif not isd(f[i]):
            return False
    return True

def s_price(f: bytes) -> bool:
    n = len(f)
    if n < 4 or n > 7:
        return False
    if f[n - 3] != 46:
        return False
    for i in range(n):
        if i != n - 3:
            if not isd(f[i]):
                return False
    return True

def s_seat(f: bytes) -> bool:
    n = len(f)
    if n < 2 or n > 4:
        return False
    if not isup(f[0]):
        return False
    for i in range(1, n):
        if not isd(f[i]):
            return False
    return True

def s_buyer(f: bytes) -> bool:
    n = len(f)
    if n < 4 or n > 12:
        return False
    if not islow(f[0]):
        return False
    for i in range(n):
        if not (islow(f[i]) or isd(f[i])):
            return False
    return True

def v_event(f: bytes) -> bool:
    s = 0
    for i in range(6):
        d = f[i] - 48
        if i % 2 == 0:
            s += 3 * d
        else:
            s += d
    return s % 10 == 0

def v_date(f: bytes) -> bool:
    y = int(f[0:4])
    m = int(f[5:7])
    d = int(f[8:10])
    if y < 2000 or y > 2099 or m < 1 or (m > 12) or (d < 1):
        return False
    dm = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    last = dm[m - 1]
    if m == 2 and y % 4 == 0:
        last = 29
    return d <= last

def v_time(f: bytes) -> bool:
    return int(f[0:2]) <= 23 and int(f[3:5]) <= 59

def v_price(f: bytes) -> bool:
    n = len(f)
    if f[0] == 48 and n - 3 > 1:
        return False
    c = int(f[0:n - 3]) * 100 + int(f[n - 2:n])
    return c % 5 == 0

def price_cents(f: bytes) -> int:
    n = len(f)
    return int(f[0:n - 3]) * 100 + int(f[n - 2:n])

def vnz(f: bytes) -> bool:
    return not (f[0] == 48 and len(f) > 1)

def v_seat(f: bytes) -> bool:
    return f[1] != 48

def rec(st: State, t: bytes, f: list[bytes]) -> int:
    n = len(f)
    if t == b'V':
        if n != 3:
            return 3
        if not (s_code(f[0]) and s_name(f[1]) and digits(f[2], 1, 6)):
            return 3
        if not vnz(f[2]):
            return 4
        cap = int(f[2])
        if cap < 1 or cap > 100000:
            return 4
        code = f[0].decode()
        if code in st.vidx:
            return 6
        st.vidx[code] = len(st.vcode)
        st.vcode.append(code)
        st.vcap.append(cap)
        st.vnev.append(0)
        st.vtix.append(0)
        st.vrev.append(0)
        st.nrec += 1
        return 0
    if t == b'E':
        if n != 5:
            return 3
        if not (digits(f[0], 6, 6) and s_code(f[1]) and s_date(f[2]) and s_time(f[3]) and s_price(f[4])):
            return 3
        if not (v_event(f[0]) and v_date(f[2]) and v_time(f[3]) and v_price(f[4])):
            return 4
        code = f[1].decode()
        if code not in st.vidx:
            return 5
        num = int(f[0])
        if num in st.evidx:
            return 6
        st.evidx[num] = len(st.evnum)
        st.evnum.append(num)
        st.evven.append(st.vidx[code])
        st.evprice.append(price_cents(f[4]))
        st.evsold.append(0)
        st.vnev[st.vidx[code]] += 1
        st.nrec += 1
        return 0
    if t == b'S':
        if n != 3:
            return 3
        if not (digits(f[0], 6, 6) and s_seat(f[1]) and s_buyer(f[2])):
            return 3
        if not (v_event(f[0]) and v_seat(f[1])):
            return 4
        num = int(f[0])
        if num not in st.evidx:
            return 5
        key = f[0].decode() + ':' + f[1].decode()
        if key in st.seats:
            return 6
        e = st.evidx[num]
        v = st.evven[e]
        if st.evsold[e] >= st.vcap[v]:
            return 7
        st.seats.add(key)
        st.evsold[e] += 1
        st.vtix[v] += 1
        st.vrev[v] += st.evprice[e]
        st.rev += st.evprice[e]
        st.ns += 1
        st.nrec += 1
        return 0
    if t == b'R':
        if n != 2:
            return 3
        if not (digits(f[0], 6, 6) and s_seat(f[1])):
            return 3
        if not (v_event(f[0]) and v_seat(f[1])):
            return 4
        num = int(f[0])
        if num not in st.evidx:
            return 5
        key = f[0].decode() + ':' + f[1].decode()
        if key not in st.seats:
            return 5
        e = st.evidx[num]
        v = st.evven[e]
        st.seats.remove(key)
        st.evsold[e] -= 1
        st.vtix[v] -= 1
        st.vrev[v] -= st.evprice[e]
        st.rev -= st.evprice[e]
        st.nr += 1
        st.nrec += 1
        return 0
    return 3

def money(x: int) -> str:
    return f'{x // 100}.{x % 100:02d}'

def main() -> int:
    if len(sys.argv) != 2:
        return 1
    data = b''
    try:
        data = read_bytes(sys.argv[1])
    except OSError as e0:
        return 1
    st = State({}, [], [], [], [], [], {}, [], [], [], [], set(), 0, 0, 0, 0)
    total = len(data)
    pos = 0
    lineno = 0
    ended = False
    while pos < total:
        q = pos
        while q < total and data[q] != 10:
            q += 1
        ln = data[pos:q]
        pos = q + 1
        lineno += 1
        if lineno == 1:
            if ln != b'TKT/1':
                print('line 1: header')
                return 2
            continue
        if ended:
            print(f'line {lineno}: summary')
            return 8
        fields: list[bytes] = []
        s = 0
        for i in range(len(ln)):
            if ln[i] == 124:
                fields.append(ln[s:i])
                s = i + 1
        fields.append(ln[s:len(ln)])
        t = fields[0]
        rest: list[bytes] = []
        for i in range(1, len(fields)):
            rest.append(fields[i])
        if t == b'END':
            if len(rest) != 2:
                print(f'line {lineno}: syntax')
                return 3
            if not (digits(rest[0], 1, 9) and digits(rest[1], 1, 12)):
                print(f'line {lineno}: syntax')
                return 3
            if not (vnz(rest[0]) and vnz(rest[1])):
                print(f'line {lineno}: value')
                return 4
            if int(rest[0]) != st.nrec or int(rest[1]) != st.rev:
                print(f'line {lineno}: summary')
                return 8
            ended = True
            continue
        r = rec(st, t, rest)
        if r != 0:
            names = ['', '', 'header', 'syntax', 'value', 'reference', 'duplicate', 'capacity', 'summary']
            print(f'line {lineno}: {names[r]}')
            return r
    if lineno == 0:
        print('line 1: header')
        return 2
    if not ended:
        print(f'line {lineno + 1}: summary')
        return 8
    print(f'venues {len(st.vcode)} events {len(st.evnum)} sold {st.ns} refunds {st.nr}')
    print(f'revenue {money(st.rev)}')
    vi = [i for i in range(len(st.vcode))]
    codes = st.vcode
    vi.sort(key=lambda i: codes[i])
    for i in vi:
        print(f'{st.vcode[i]} events={st.vnev[i]} tickets={st.vtix[i]} revenue={money(st.vrev[i])}')
    ei = [i for i in range(len(st.evnum))]
    sold = st.evsold
    nums = st.evnum
    ei.sort(key=lambda i: (-sold[i], nums[i]))
    k = 0
    for i in ei:
        if k >= 3:
            break
        print(f'top {st.evnum[i]:06d} {st.evsold[i]}')
        k += 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
