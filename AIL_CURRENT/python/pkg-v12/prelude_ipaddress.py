# -*- coding: utf-8 -*-
# prelude_ipaddress.py -- `ipaddress.IPv4Address` as Python source (stdtop.py injects it).
#
# Plain Python in the subset the general path builds, and a module CPython imports as it stands, so the tests
# compare it with ipaddress.IPv4Address directly. The parsing and the error texts are those of CPython 3.12's
# ipaddress.py. The properties are plain attributes computed when the address is made. Not built, refused by
# name in stdtop.py: is_private / is_global (their lists differ between 3.12 patch releases), ipv6, IPv4Network,
# IPv4Interface, ip_address(), ip_network(), the format types b / x / X / n.


class AddressValueError(ValueError):
    pass


def _ail_ip_octet(s: str) -> int:
    # one octet of a dotted quad; -1 when it is no number (the text of the error is in _ail_ip_octet_error)
    if s == "":
        return -1
    if not (s.isascii() and s.isdigit()):
        return -1
    if len(s) > 3:
        return -1
    if s != "0" and s[0] == "0":
        return -1
    v = int(s)
    if v > 255:
        return -1
    return v


def _ail_ip_octet_error(s: str) -> str:
    if s == "":
        return "Empty octet not permitted"
    if not (s.isascii() and s.isdigit()):
        return "Only decimal digits permitted in %r" % s
    if len(s) > 3:
        return "At most 3 characters permitted in %r" % s
    if s != "0" and s[0] == "0":
        return "Leading zeros are not permitted in %r" % s
    return "Octet %d (> 255) not permitted" % int(s)


def _ail_ip_parse(text: str) -> int:
    if text == "":
        raise AddressValueError("Address cannot be empty")
    octets = text.split(".")
    if len(octets) != 4:
        raise AddressValueError("Expected 4 octets in %r" % text)
    v = 0
    for o in octets:
        n = _ail_ip_octet(o)
        if n < 0:
            raise AddressValueError("%s in %r" % (_ail_ip_octet_error(o), text))
        v = v * 256 + n
    return v


def _ail_ip_str(v: int) -> str:
    return "%d.%d.%d.%d" % (v >> 24, (v >> 16) & 255, (v >> 8) & 255, v & 255)


class IPv4Address:
    def __init__(self, address):
        v = 0
        if isinstance(address, bool):
            if address:
                v = 1
        elif isinstance(address, int):
            if address < 0:
                raise AddressValueError("%d (< 0) is not permitted as an IPv4 address" % address)
            if address > 4294967295:
                raise AddressValueError("%d (>= 2**32) is not permitted as an IPv4 address" % address)
            v = address
        elif isinstance(address, bytes):
            if len(address) != 4:
                raise AddressValueError("%r (len %d != 4) is not permitted as an IPv4 address" % (address, len(address)))
            for b in address:
                v = v * 256 + b
        else:
            text = str(address)
            if "/" in text:
                raise AddressValueError("Unexpected '/' in %r" % address)
            v = _ail_ip_parse(text)
        self._ip = v
        self.version = 4
        self.max_prefixlen = 32
        self.is_multicast = (v >> 28) == 14
        self.is_unspecified = v == 0
        self.is_loopback = (v >> 24) == 127
        self.is_link_local = (v >> 16) == 43518
        self.is_reserved = (v >> 28) == 15
        self.compressed = _ail_ip_str(v)
        self.exploded = self.compressed
        self.reverse_pointer = "%d.%d.%d.%d.in-addr.arpa" % (v & 255, (v >> 8) & 255, (v >> 16) & 255, v >> 24)
        self.packed = bytes([v >> 24, (v >> 16) & 255, (v >> 8) & 255, v & 255])

    def __int__(self) -> int:
        return self._ip

    def __str__(self) -> str:
        return _ail_ip_str(self._ip)

    def __repr__(self) -> str:
        return "IPv4Address('%s')" % _ail_ip_str(self._ip)

    def __hash__(self):
        return hash(hex(self._ip))

    def __eq__(self, other):
        if isinstance(other, IPv4Address):
            return self._ip == other._ip
        return False

    def __lt__(self, other):
        if not isinstance(other, IPv4Address):
            raise TypeError("'<' not supported between instances of 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return self._ip < other._ip

    def __le__(self, other):
        if not isinstance(other, IPv4Address):
            raise TypeError("'<=' not supported between instances of 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return self._ip <= other._ip

    def __gt__(self, other):
        if not isinstance(other, IPv4Address):
            raise TypeError("'>' not supported between instances of 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return self._ip > other._ip

    def __ge__(self, other):
        if not isinstance(other, IPv4Address):
            raise TypeError("'>=' not supported between instances of 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return self._ip >= other._ip

    def __add__(self, other):
        if not isinstance(other, int):
            raise TypeError("unsupported operand type(s) for +: 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return IPv4Address(self._ip + other)

    def __sub__(self, other):
        if not isinstance(other, int):
            raise TypeError("unsupported operand type(s) for -: 'IPv4Address' and '%s'" % _ail_ip_tname(other))
        return IPv4Address(self._ip - other)

    def __format__(self, spec):
        if spec == "" or spec[-1] == "s":
            return format(_ail_ip_str(self._ip), spec)
        n = len(spec)
        i = 0
        alt = ""
        grp = ""
        if i < n and spec[i] == "#":
            alt = "#"
            i = i + 1
        if i < n and spec[i] == "_":
            grp = "_"
            i = i + 1
        if i != n - 1 or not (spec[i] == "x" or spec[i] == "b" or spec[i] == "n" or spec[i] == "X"):
            raise TypeError("unsupported format string passed to IPv4Address.__format__")
        base = spec[i]
        if base == "n":
            base = "b"
        padlen = 32
        if base != "b":
            padlen = 8
        if grp != "":
            padlen = padlen + padlen // 4 - 1
        if alt != "":
            padlen = padlen + 2
        return format(self._ip, "%s0%d%s%s" % (alt, padlen, grp, base))


def _ail_ip_tname(x) -> str:
    if x is None:
        return "NoneType"
    return type(x).__name__
