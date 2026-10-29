# prelude_struct.py -- `struct` pack/unpack/unpack_from/calcsize for the integer formats and x padding
# (structlib.py injects it). Floats, pascal strings, chars, bools and strings are refused at compile time.


class _AilStructError(Exception):
    pass


class _AilStructPlan:
    ats: list[int]
    sizes: list[int]
    signeds: list[int]
    kinds: list[int]
    counts: list[int]
    codes: list[int]
    total: int
    big: bool

    def __init__(self) -> None:
        self.ats = []
        self.sizes = []
        self.signeds = []
        self.kinds = []
        self.counts = []
        self.codes = []
        self.total = 0
        self.big = False


def _ail_struct_add(plan: _AilStructPlan, at: int, size: int, signed: int, kind: int, count: int, code: int) -> None:
    plan.ats.append(at)
    plan.sizes.append(size)
    plan.signeds.append(signed)
    plan.kinds.append(kind)
    plan.counts.append(count)
    plan.codes.append(code)


def _ail_struct_bad(char: str) -> None:
    raise _AilStructError("bad char in struct format")


def _ail_struct_plan(fmt: str) -> _AilStructPlan:
    plan = _AilStructPlan()
    native = True
    pos = 0
    if len(fmt) > 0 and (fmt[0] == "@" or fmt[0] == "=" or fmt[0] == "<" or fmt[0] == ">" or fmt[0] == "!"):
        if fmt[0] == ">" or fmt[0] == "!":
            plan.big = True
        if fmt[0] == "=" or fmt[0] == "<" or fmt[0] == ">" or fmt[0] == "!":
            native = False
        pos = 1
    offset = 0
    align = 1
    while pos < len(fmt):
        ch = fmt[pos]
        if ch == " " or ch == "\t" or ch == "\n":
            pos = pos + 1
            continue
        if ch == "@" or ch == "=" or ch == "<" or ch == ">" or ch == "!":
            _ail_struct_bad(ch)
        start = pos
        while pos < len(fmt) and fmt[pos] >= "0" and fmt[pos] <= "9":
            pos = pos + 1
        if pos == start:
            count = 1
        else:
            count = int(fmt[start:pos])
        if pos >= len(fmt):
            raise _AilStructError("repeat count given without format specifier")
        ch = fmt[pos]
        pos = pos + 1
        size = 0
        signed = 0
        kind = 0
        if ch in "bBhHiIlLqQnNP":
            if ch == "b" or ch == "h" or ch == "i" or ch == "l" or ch == "q" or ch == "n":
                signed = 1
            if ch == "b" or ch == "B":
                size = 1
            elif ch == "h" or ch == "H":
                size = 2
            elif ch == "i" or ch == "I":
                size = 4
            elif ch == "l" or ch == "L":
                if native:
                    size = 8
                else:
                    size = 4
            else:
                size = 8
        elif ch == "x":
            size = count
            kind = 3
        elif ch == "f" or ch == "d" or ch == "e" or ch == "p":
            raise _AilStructError("struct format code " + ch + " is not built")
        else:
            raise _AilStructError("struct format code " + ch + " is not built")
        item_count = count
        if kind == 3:
            _ail_struct_add(plan, offset, size, signed, kind, item_count, ord(ch))
            offset = offset + size
        else:
            if native and size > 1:
                if align < size:
                    align = size
                pad = offset % size
                if pad != 0:
                    offset = offset + (size - pad)
            _ail_struct_add(plan, offset, size, signed, kind, item_count, ord(ch))
            offset = offset + size * item_count
    plan.total = offset
    return plan


def _ail_struct_order(plan: _AilStructPlan) -> str:
    if plan.big:
        return "big"
    return "little"


def _ail_struct_size(fmt: str) -> int:
    plan = _ail_struct_plan(fmt)
    return plan.total


def _ail_struct_int(value, signed: int) -> int:
    if isinstance(value, bool):
        if value:
            return 1
        return 0
    if not isinstance(value, int):
        raise _AilStructError("required argument is not an integer")
    return value


def _ail_struct_int_arg(value) -> int:
    return _ail_struct_int(value, 0)


def _ail_struct_range(value: int, size: int, signed: int, code: int) -> None:
    lo = 0
    hi = 255
    label = "'" + chr(code) + "' format requires"
    if size == 1:
        if signed:
            lo = -128
            hi = 127
        else:
            lo = 0
            hi = 255
    elif size == 2:
        if signed:
            lo = -32768
            hi = 32767
        else:
            lo = 0
            hi = 65535
    elif size == 4:
        if signed:
            lo = -2147483648
            hi = 2147483647
        else:
            lo = 0
            hi = 4294967295
    else:
        if signed:
            lo = -9223372036854775808
            hi = 9223372036854775807
        else:
            lo = 0
            hi = 9223372036854775807
            if code == ord("P"):
                lo = -9223372036854775808
    if value < lo or value > hi:
        raise _AilStructError(label + " " + str(lo) + " <= number <= " + str(hi))


def _ail_struct_pack(fmt: str, values: list[int]) -> bytes:
    plan = _ail_struct_plan(fmt)
    order = _ail_struct_order(plan)
    out = bytearray()
    index = 0
    expected = 0
    for i in range(len(plan.kinds)):
        if plan.kinds[i] != 3:
            expected = expected + plan.counts[i]
    for i in range(len(plan.kinds)):
        size = plan.sizes[i]
        count = plan.counts[i]
        kind = plan.kinds[i]
        signed = plan.signeds[i]
        code = plan.codes[i]
        while len(out) < plan.ats[i]:
            out.append(0)
        if kind == 3:
            k = 0
            while k < count:
                out.append(0)
                k = k + 1
        else:
            k = 0
            while k < count:
                if index >= len(values):
                    raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
                v = values[index]
                index = index + 1
                _ail_struct_range(v, size, signed, code)
                if size == 8 and signed == 0 and v < 0:
                    out.extend(v.to_bytes(size, order, signed=True))
                else:
                    out.extend(v.to_bytes(size, order, signed=signed != 0))
                k = k + 1
    if index != len(values):
        raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
    return bytes(out)


def _ail_struct_check(data: bytes, offset: int, total: int, from_unpack: bool) -> int:
    if not from_unpack:
        if len(data) != total:
            raise _AilStructError("unpack requires a buffer of " + str(total) + " bytes")
        return offset
    length = len(data)
    if offset < 0:
        if offset < -length:
            raise _AilStructError("offset " + str(offset) + " out of range for " + str(length) + "-byte buffer")
        if length < offset + length + total:
            raise _AilStructError("not enough data to unpack " + str(total) + " bytes at offset " + str(offset))
        return offset + length
    if length < offset + total:
        raise _AilStructError("unpack_from requires a buffer of at least " + str(offset + total) + " bytes for unpacking " + str(total) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(length) + ")")
    return offset


def _ail_struct_unpack(fmt: str, data: bytes, offset: int, from_unpack: bool) -> list[int]:
    plan = _ail_struct_plan(fmt)
    offset = _ail_struct_check(data, offset, plan.total, from_unpack)
    order = _ail_struct_order(plan)
    out = []
    for i in range(len(plan.kinds)):
        if plan.kinds[i] == 3:
            continue
        at = plan.ats[i] + offset
        k = 0
        while k < plan.counts[i]:
            out.append(int.from_bytes(bytes(data[at:at + plan.sizes[i]]), order, signed=plan.signeds[i] != 0))
            at = at + plan.sizes[i]
            k = k + 1
    return out
