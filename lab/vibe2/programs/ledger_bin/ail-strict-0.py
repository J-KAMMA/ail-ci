import sys


def read_var(data: bytes, pos: int, end: int) -> tuple[bool, str, int, int]:
    val: int = 0
    shift: int = 0
    i: int = 0
    b: int = 0
    while True:
        if pos + i >= end:
            return (False, "truncated", 0, pos + i)
        b = data[pos + i]
        if i == 4 and (b & 0x80) != 0:
            return (False, "varint", 0, pos + i + 1)
        val = val | ((b & 0x7F) << shift)
        if (b & 0x80) == 0:
            if i > 0 and b == 0:
                return (False, "varint", 0, pos + i + 1)
            if val > 4294967295:
                return (False, "varint", 0, pos + i + 1)
            return (True, "", val, pos + i + 1)
        shift += 7
        i += 1


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(1)
    path: str = sys.argv[1]
    data: bytes = b""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        sys.exit(1)

    n: int = len(data)
    if n < 6:
        print("error at offset 0: header")
        sys.exit(2)
    if (data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58
            or data[3] != 0x46 or data[4] != 0x02 or (data[5] & 0xFE) != 0):
        print("error at offset 0: header")
        sys.exit(2)

    strict: bool = (data[5] & 1) != 0

    records: list[tuple[int, int, int, int, int, str]] = []
    pos: int = 6
    err: bool = False
    ekind: str = ""
    eoff: int = 0
    start: int = 0
    op: int = 0
    a: int = 0
    b: int = 0
    c: int = 0
    nm: str = ""
    res: tuple[bool, str, int, int] = (True, "", 0, 0)
    nl: int = 0
    j: int = 0
    ch: int = 0
    bad: bool = False
    ln: int = 0
    chk: int = 0
    cc: int = 0
    k: int = 0

    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        if op < 1 or op > 5:
            err = True
            ekind = "opcode"
            eoff = start
            break
        a = 0
        b = 0
        c = 0
        nm = ""
        if op == 1:
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            a = res[2]
            pos = res[3]
            if pos >= n:
                err = True
                ekind = "truncated"
                eoff = start
                break
            nl = data[pos]
            pos += 1
            if nl < 1 or nl > 32:
                err = True
                ekind = "name"
                eoff = start
                break
            j = 0
            bad = False
            while j < nl:
                if pos >= n:
                    err = True
                    ekind = "truncated"
                    eoff = start
                    bad = True
                    break
                ch = data[pos]
                pos += 1
                if ch < 0x21 or ch > 0x7E:
                    err = True
                    ekind = "name"
                    eoff = start
                    bad = True
                    break
                nm += chr(ch)
                j += 1
            if bad:
                break
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            b = res[2]
            pos = res[3]
        elif op == 2:
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            a = res[2]
            pos = res[3]
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            b = res[2]
            pos = res[3]
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            c = res[2]
            pos = res[3]
        elif op == 3:
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            a = res[2]
            pos = res[3]
        elif op == 4:
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            a = res[2]
            pos = res[3]
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            b = res[2]
            pos = res[3]
        else:
            res = read_var(data, pos, n)
            if not res[0]:
                err = True
                ekind = res[1]
                eoff = start
                break
            ln = res[2]
            pos = res[3]
            if n - pos < ln:
                err = True
                ekind = "truncated"
                eoff = start
                break
            pos += ln

        if pos >= n:
            err = True
            ekind = "truncated"
            eoff = start
            break
        chk = data[pos]
        pos += 1
        cc = 0
        k = start
        while k < pos - 1:
            cc = (cc * 31 + data[k]) % 251
            k += 1
        if cc != chk:
            err = True
            ekind = "check"
            eoff = start
            break
        records.append((start, op, a, b, c, nm))

    if err:
        print(f"error at offset {eoff}: {ekind}")
        sys.exit(2)

    acc_name: dict[int, str] = {}
    acc_bal: dict[int, int] = {}
    acc_open: dict[int, int] = {}
    dup: int = 0
    unk: int = 0
    shutc: int = 0
    selfc: int = 0
    fundsc: int = 0
    roff: int = 0
    rej: bool = False
    reason: str = ""
    rec: tuple[int, int, int, int, int, str] = (0, 0, 0, 0, 0, "")

    for rec in records:
        roff = rec[0]
        op = rec[1]
        a = rec[2]
        b = rec[3]
        c = rec[4]
        nm = rec[5]
        rej = False
        reason = ""
        if op == 1:
            if a in acc_name:
                rej = True
                reason = "dup"
            else:
                acc_name[a] = nm
                acc_bal[a] = b
                acc_open[a] = 1
        elif op == 2:
            if a not in acc_name or b not in acc_name:
                rej = True
                reason = "unknown"
            elif acc_open[a] == 0 or acc_open[b] == 0:
                rej = True
                reason = "shut"
            elif a == b:
                rej = True
                reason = "self"
            elif c > acc_bal[a]:
                rej = True
                reason = "funds"
            else:
                acc_bal[a] = acc_bal[a] - c
                acc_bal[b] = acc_bal[b] + c
        elif op == 3:
            if a not in acc_name:
                rej = True
                reason = "unknown"
            elif acc_open[a] == 0:
                rej = True
                reason = "shut"
            else:
                acc_open[a] = 0
        elif op == 4:
            if a not in acc_name:
                rej = True
                reason = "unknown"
            elif acc_open[a] == 0:
                rej = True
                reason = "shut"
            else:
                acc_bal[a] = acc_bal[a] + b
        if rej:
            if strict:
                print(f"rejected at offset {roff}: {reason}")
                sys.exit(3)
            if reason == "dup":
                dup += 1
            elif reason == "unknown":
                unk += 1
            elif reason == "shut":
                shutc += 1
            elif reason == "self":
                selfc += 1
            else:
                fundsc += 1

    total: int = 0
    open_count: int = 0
    shut_count: int = 0
    for k in sorted(acc_name.keys()):
        if acc_open[k] == 1:
            open_count += 1
        else:
            shut_count += 1
        total += acc_bal[k]

    cand: list[tuple[int, int, str]] = []
    for k in acc_name.keys():
        if acc_open[k] == 1:
            cand.append((0 - acc_bal[k], k, acc_name[k]))
    cand.sort()

    g: int = 0
    for k in sorted(acc_name.keys()):
        g = (g * 1000003 + k * 7 + acc_bal[k]) % 1000000007

    print(f"records: {len(records)}")
    print(f"accounts: {open_count} open, {shut_count} shut")
    print(f"rejected: dup={dup} unknown={unk} shut={shutc} self={selfc} funds={fundsc}")
    print(f"total: {total}")
    i2: int = 0
    pr: int = 0
    while i2 < len(cand) and i2 < 5:
        pr = 0 - cand[i2][0]
        print(f"top: {cand[i2][1]} {cand[i2][2]} {pr}")
        i2 += 1
    print(f"digest: {g}")


if __name__ == "__main__":
    main()
