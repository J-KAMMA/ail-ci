import sys


def pack_data(data):
    n = len(data)
    out = bytearray()
    out.extend(b"EP1")
    out.extend(n.to_bytes(4, "little"))

    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF

    lit = bytearray()
    table = {}
    next_add = 0
    expire = 0
    i = 0

    while i < n:
        while next_add < i:
            p = next_add
            if p + 4 <= n:
                key = data[p:p + 4]
                lst = table.get(key)
                if lst is None:
                    table[key] = [p]
                else:
                    lst.append(p)
                    if len(lst) > 8:
                        lst.pop(0)
            next_add += 1

        low = i - 65535
        while expire < low:
            q = expire
            if q + 4 <= n:
                key = data[q:q + 4]
                lst = table.get(key)
                if lst is not None:
                    if q in lst:
                        lst.remove(q)
                    if len(lst) == 0:
                        del table[key]
            expire += 1

        if i + 4 <= n:
            key = data[i:i + 4]
            lst = table.get(key)
            best_m = 0
            best_p = -1
            if lst is not None:
                limit = n - i
                if limit > 131:
                    limit = 131
                cnt = 0
                j = len(lst) - 1
                while j >= 0:
                    p = lst[j]
                    if i - p <= 65535:
                        mm = 4
                        while mm < limit and data[p + mm] == data[i + mm]:
                            mm += 1
                        if mm > best_m:
                            best_m = mm
                            best_p = p
                    cnt += 1
                    if cnt == 8:
                        break
                    j -= 1

            if best_m >= 4:
                if len(lit) > 0:
                    out.append(len(lit) - 1)
                    out.extend(lit)
                    lit = bytearray()
                out.append(128 + (best_m - 4))
                dist = i - best_p
                out.append((dist >> 8) & 255)
                out.append(dist & 255)
                i += best_m
                continue

        lit.append(data[i])
        if len(lit) == 128:
            out.append(127)
            out.extend(lit)
            lit = bytearray()
        i += 1

    if len(lit) > 0:
        out.append(len(lit) - 1)
        out.extend(lit)

    out.extend(h.to_bytes(4, "little"))
    return out


def unpack_data(data):
    total = len(data)
    if total < 3:
        return None
    if data[0:3] != b"EP1":
        return None
    if total < 7:
        return None

    n = int.from_bytes(data[3:7], "little")
    pos = 7
    out = bytearray()

    while len(out) < n:
        if pos >= total:
            return None
        c = data[pos]
        pos += 1
        if c < 128:
            cnt = c + 1
            if pos + cnt > total:
                return None
            if len(out) + cnt > n:
                return None
            out.extend(data[pos:pos + cnt])
            pos += cnt
        else:
            cnt = (c - 128) + 4
            if pos + 2 > total:
                return None
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            if dist == 0 or dist > len(out):
                return None
            if len(out) + cnt > n:
                return None
            k = 0
            while k < cnt:
                out.append(out[-dist])
                k += 1

    if pos + 4 > total:
        return None

    expected = int.from_bytes(data[pos:pos + 4], "little")
    pos += 4
    if pos != total:
        return None

    h = 0
    for b in out:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    if h != expected:
        return None

    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "pack":
        data = sys.stdin.buffer.read()
        result = pack_data(data)
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()
        sys.exit(0)

    if cmd == "unpack":
        data = sys.stdin.buffer.read()
        result = unpack_data(data)
        if result is None:
            sys.exit(2)
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
