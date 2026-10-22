# prelude_ipaddress.py -- `ipaddress.IPv4Address` as Python source (library batch 6, stdlib6.py injects it).
#
# Ordinary Python in the subset both compile paths build (a class with operator methods, no imports).
# The behaviour follows CPython 3.12's ipaddress.py: the string parser's leading-zero and octet rules,
# int/bytes construction, the ordering, and the address properties (`packed`, `is_private`, ...).


def _ail_ip_dotted(v: int) -> str:
    return str((v >> 24) & 255) + "." + str((v >> 16) & 255) + "." + str((v >> 8) & 255) + "." + str(v & 255)


def _ail_ip_parse(text: str) -> int:
    if text == "":
        raise ValueError("Address cannot be empty")
    parts = text.split(".")
    if len(parts) != 4:
        raise ValueError("Expected 4 octets in " + repr(text))
    out = 0
    for part in parts:
        if part == "":
            raise ValueError("Empty octet not permitted in " + repr(text))
        i = 0
        while i < len(part):
            if part[i] < "0" or part[i] > "9":
                raise ValueError("Only decimal digits permitted in " + repr(part) + " in " + repr(text))
            i = i + 1
        if len(part) > 1 and part[0] == "0":
            raise ValueError("Leading zeros are not permitted in " + repr(part) + " in " + repr(text))
        n = 0
        i = 0
        while i < len(part):
            n = n * 10 + (ord(part[i]) - 48)
            i = i + 1
        if n > 255:
            raise ValueError("Octet " + str(n) + " (> 255) not permitted in " + repr(text))
        out = out * 256 + n
    return out


def _ail_ip_in(v: int, net: int, mask: int) -> bool:
    return (v & mask) == net


def _ail_ip_private(v: int) -> bool:
    if _ail_ip_in(v, 0, 4278190080):
        return True
    if _ail_ip_in(v, 167772160, 4278190080):
        return True
    if _ail_ip_in(v, 2130706432, 4278190080):
        return True
    if _ail_ip_in(v, 2851995648, 4294901760):
        return True
    if _ail_ip_in(v, 2886729728, 4293918720):
        return True
    if _ail_ip_in(v, 3221225472, 4294967288):
        return True
    if _ail_ip_in(v, 3221225642, 4294967294):
        return True
    if _ail_ip_in(v, 3221225984, 4294967040):
        return True
    if _ail_ip_in(v, 3232235520, 4294901760):
        return True
    if _ail_ip_in(v, 3323068416, 4294836224):
        return True
    if _ail_ip_in(v, 3325256704, 4294967040):
        return True
    if _ail_ip_in(v, 3405803776, 4294967040):
        return True
    if _ail_ip_in(v, 4026531840, 4026531840):
        return True
    if v == 4294967295:
        return True
    return False


def _ail_ip_shared(v: int) -> bool:
    return _ail_ip_in(v, 1681915904, 4290772992)


class _AilIPv4Address:
    def __init__(self, address):
        v = 0
        if isinstance(address, bool):
            v = int(address)
        elif isinstance(address, int):
            v = address
            if v < 0:
                raise ValueError(str(v) + " (< 0) is not permitted as an IPv4 address")
            if v >= 4294967296:
                raise ValueError(str(v) + " (>= 2**32) is not permitted as an IPv4 address")
        elif isinstance(address, bytes):
            if len(address) != 4:
                raise ValueError(repr(address) + " (len " + str(len(address)) + " != 4) is not permitted as an IPv4 address")
            v = (address[0] * 16777216) + (address[1] * 65536) + (address[2] * 256) + address[3]
        else:
            v = _ail_ip_parse(str(address))
        self._value = v
        self.version = 4
        self.max_prefixlen = 32
        self.compressed = _ail_ip_dotted(v)
        self.exploded = self.compressed
        buf = bytearray()
        buf.append((v >> 24) & 255)
        buf.append((v >> 16) & 255)
        buf.append((v >> 8) & 255)
        buf.append(v & 255)
        self.packed = bytes(buf)
        self.reverse_pointer = str(v & 255) + "." + str((v >> 8) & 255) + "." + str((v >> 16) & 255) + "." + str((v >> 24) & 255) + ".in-addr.arpa"
        self.is_private = _ail_ip_private(v)
        self.is_reserved = _ail_ip_in(v, 4026531840, 4026531840)
        self.is_loopback = _ail_ip_in(v, 2130706432, 4278190080)
        self.is_link_local = _ail_ip_in(v, 2851995648, 4294901760)
        self.is_multicast = _ail_ip_in(v, 3758096384, 4026531840)
        self.is_unspecified = v == 0
        self.is_global = not (self.is_private or self.is_reserved or self.is_loopback or self.is_link_local
                              or self.is_multicast or self.is_unspecified or _ail_ip_shared(v))

    def __str__(self) -> str:
        return self.compressed

    def __repr__(self) -> str:
        return "IPv4Address('" + self.compressed + "')"

    def __int__(self) -> int:
        return self._value

    def __index__(self) -> int:
        return self._value

    def __eq__(self, other) -> bool:
        if isinstance(other, _AilIPv4Address):
            return self._value == other._value
        return False

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other) -> bool:
        if not isinstance(other, _AilIPv4Address):
            raise TypeError("'<' not supported between instances of 'IPv4Address' and '" + type(other).__name__ + "'")
        return self._value < other._value

    def __le__(self, other) -> bool:
        if not isinstance(other, _AilIPv4Address):
            raise TypeError("'<=' not supported between instances of 'IPv4Address' and '" + type(other).__name__ + "'")
        return self._value <= other._value

    def __gt__(self, other) -> bool:
        if not isinstance(other, _AilIPv4Address):
            raise TypeError("'>' not supported between instances of 'IPv4Address' and '" + type(other).__name__ + "'")
        return self._value > other._value

    def __ge__(self, other) -> bool:
        if not isinstance(other, _AilIPv4Address):
            raise TypeError("'>=' not supported between instances of 'IPv4Address' and '" + type(other).__name__ + "'")
        return self._value >= other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __add__(self, other):
        if isinstance(other, int):
            return _AilIPv4Address(self._value + other)
        if isinstance(other, _AilIPv4Address):
            raise TypeError("unsupported operand type(s) for +: 'IPv4Address' and 'IPv4Address'")
        raise TypeError("unsupported operand type(s) for +: 'IPv4Address' and '" + type(other).__name__ + "'")

    def __sub__(self, other):
        if isinstance(other, int):
            return _AilIPv4Address(self._value - other)
        if isinstance(other, _AilIPv4Address):
            raise TypeError("unsupported operand type(s) for -: 'IPv4Address' and 'IPv4Address'")
        raise TypeError("unsupported operand type(s) for -: 'IPv4Address' and '" + type(other).__name__ + "'")
