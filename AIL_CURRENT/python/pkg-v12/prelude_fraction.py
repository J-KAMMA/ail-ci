# -*- coding: utf-8 -*-
# prelude_fraction.py -- `fractions.Fraction` as Python source (library batch 5, fraclib.py injects it).
#
# Plain Python in the subset the general path builds (classes with operator methods: dunderrt.py), and
# a module CPython imports as it stands, so the tests compare it with fractions.Fraction directly. The
# algorithms are the ones of CPython 3.12's fractions.py (gcd-reduced add / mul / div, limit_denominator
# by continued fractions). The one declared difference: int is 64-bit here, so a numerator or denominator
# beyond it is an OverflowError (the program ends, as for any int).


def _ail_fr_gcd(a: int, b: int) -> int:
    if a < 0:
        a = -a
    if b < 0:
        b = -b
    while b != 0:
        t = a % b
        a = b
        b = t
    return a


def _ail_fr_tname(x) -> str:
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, dict):
        return "dict"
    if isinstance(x, tuple):
        return "tuple"
    if x is None:
        return "NoneType"
    return "object"


def _ail_fr_representable(x: int) -> bool:
    # a nonzero integer whose odd part has at most 53 bits is a float exactly
    if x < 0:
        x = -x
    if x == 0:
        return True
    while x % 2 == 0:
        x = x // 2
    return x < 9007199254740992


def _ail_fr_to_float(n: int, d: int) -> float:
    # n / d correctly rounded, as CPython's int true division
    if n == 0:
        return 0.0
    if _ail_fr_representable(n) and _ail_fr_representable(d):
        return n / d
    neg = n < 0
    if neg:
        n = -n
    # scale: 54..55 quotient bits, the remainder as a sticky bit
    e = 0
    q = n // d
    r = n % d
    while q >= 36028797018963968:
        # the integer part alone has 56+ bits: halve it, keeping a sticky bit
        if q % 2 == 1:
            r = 1
        q = q // 2
        e = e + 1
    while q < 18014398509481984:
        # double the quotient: next bit of the expansion
        if r >= d - r:
            q = q * 2 + 1
            r = r - (d - r)
        else:
            q = q * 2
            r = r + r
        e = e - 1
    # q has 55 bits; round to 53: drop 2 bits, ties to even, sticky from r
    low = q % 4
    q = q // 4
    e = e + 2
    if low > 2 or (low == 2 and (r != 0 or q % 2 == 1)):
        q = q + 1
    x = float(q)
    while e > 0:
        x = x * 2.0
        e = e - 1
    while e < 0:
        x = x / 2.0
        e = e + 1
    if neg:
        x = -x
    return x


def _ail_fr_float_parts(x: float) -> list[int]:
    if x != x:
        raise ValueError("cannot convert NaN to integer ratio")
    if x - x != 0.0:
        raise OverflowError("cannot convert Infinity to integer ratio")
    d = 1
    while x != float(int(x)):
        x = x * 2.0
        d = d * 2
    n = int(x)
    while d > 1 and n % 2 == 0:
        n = n // 2
        d = d // 2
    return [n, d]


def _ail_fr_scan(s: str, i: int) -> int:
    # end of a run of digits with single underscores between them, starting at i; i itself when none
    n = len(s)
    j = i
    while j < n:
        c = s[j]
        if "0" <= c <= "9":
            j = j + 1
        elif c == "_" and j > i and j + 1 < n and "0" <= s[j + 1] <= "9":
            j = j + 1
        else:
            break
    return j


def _ail_fr_parse(text: str) -> list[int]:
    s = text.strip()
    n = len(s)
    i = 0
    neg = False
    if i < n and (s[i] == "+" or s[i] == "-"):
        neg = s[i] == "-"
        i = i + 1
    ip_end = _ail_fr_scan(s, i)
    intpart = s[i:ip_end].replace("_", "")
    pos = ip_end
    num = 0
    den = 1
    k = pos
    while k < n and s[k].isspace():
        k = k + 1
    if k < n and s[k] == "/":
        if ip_end == i:
            raise ValueError("Invalid literal for Fraction: %r" % text)
        k = k + 1
        while k < n and s[k].isspace():
            k = k + 1
        dend = _ail_fr_scan(s, k)
        if dend == k or dend != n:
            raise ValueError("Invalid literal for Fraction: %r" % text)
        num = int(intpart)
        den = int(s[k:dend].replace("_", ""))
    else:
        frac = ""
        if pos < n and s[pos] == ".":
            fend = _ail_fr_scan(s, pos + 1)
            frac = s[pos + 1:fend].replace("_", "")
            pos = fend
        if ip_end == i and frac == "":
            raise ValueError("Invalid literal for Fraction: %r" % text)
        exp = 0
        if pos < n and (s[pos] == "e" or s[pos] == "E"):
            k = pos + 1
            eneg = False
            if k < n and (s[k] == "+" or s[k] == "-"):
                eneg = s[k] == "-"
                k = k + 1
            eend = _ail_fr_scan(s, k)
            if eend == k:
                raise ValueError("Invalid literal for Fraction: %r" % text)
            exp = int(s[k:eend].replace("_", ""))
            if eneg:
                exp = -exp
            pos = eend
        if pos != n:
            raise ValueError("Invalid literal for Fraction: %r" % text)
        num = 0
        if intpart != "":
            num = int(intpart)
        if frac != "":
            scale = 10 ** len(frac)
            num = num * scale + int(frac)
            den = den * scale
        if exp >= 0:
            num = num * 10 ** exp
        else:
            den = den * 10 ** (-exp)
    if neg:
        num = -num
    return [num, den]


class Fraction:
    def __init__(self, numerator=0, denominator=None, _ail_raw=False):
        if _ail_raw:
            self.numerator = numerator
            self.denominator = denominator
            return
        n = 0
        d = 1
        if denominator is None:
            if isinstance(numerator, Fraction):
                n = numerator.numerator
                d = numerator.denominator
            elif isinstance(numerator, int):
                n = numerator
            elif isinstance(numerator, float):
                parts = _ail_fr_float_parts(numerator)
                n = parts[0]
                d = parts[1]
            elif isinstance(numerator, str):
                parts = _ail_fr_parse(numerator)
                n = parts[0]
                d = parts[1]
            else:
                raise TypeError("argument should be a string or a Rational instance")
        else:
            if isinstance(numerator, Fraction) or isinstance(denominator, Fraction):
                if not ((isinstance(numerator, int) or isinstance(numerator, Fraction)) and (isinstance(denominator, int) or isinstance(denominator, Fraction))):
                    raise TypeError("both arguments should be Rational instances")
                a = Fraction(numerator)
                b = Fraction(denominator)
                n = a.numerator * b.denominator
                d = a.denominator * b.numerator
            elif isinstance(numerator, int) and isinstance(denominator, int):
                n = numerator
                d = denominator
            else:
                raise TypeError("both arguments should be Rational instances")
        if d == 0:
            raise ZeroDivisionError("Fraction(%s, 0)" % n)
        g = _ail_fr_gcd(n, d)
        if d < 0:
            g = -g
        self.numerator = n // g
        self.denominator = d // g

    def __repr__(self) -> str:
        return "Fraction(%s, %s)" % (self.numerator, self.denominator)

    def __str__(self) -> str:
        if self.denominator == 1:
            return str(self.numerator)
        return "%s/%s" % (self.numerator, self.denominator)

    def __float__(self) -> float:
        return _ail_fr_to_float(self.numerator, self.denominator)

    def as_integer_ratio(self):
        return (self.numerator, self.denominator)

    def is_integer(self) -> bool:
        return self.denominator == 1

    def __hash__(self):
        if self.denominator == 1:
            return self.numerator
        return self.numerator * 1000003 + self.denominator

    def __bool__(self) -> bool:
        return self.numerator != 0

    def __neg__(self):
        return Fraction(-self.numerator, self.denominator, True)

    def __pos__(self):
        return Fraction(self.numerator, self.denominator, True)

    def __abs__(self):
        return Fraction(abs(self.numerator), self.denominator, True)

    def __trunc__(self):
        if self.numerator < 0:
            return -(-self.numerator // self.denominator)
        return self.numerator // self.denominator

    def __int__(self):
        if self.numerator < 0:
            return -(-self.numerator // self.denominator)
        return self.numerator // self.denominator

    def __floor__(self):
        return self.numerator // self.denominator

    def __ceil__(self):
        return -(-self.numerator // self.denominator)

    def __round__(self, ndigits=None):
        if ndigits is None:
            fl = self.numerator // self.denominator
            rem = self.numerator % self.denominator
            if rem * 2 < self.denominator:
                return fl
            if rem * 2 > self.denominator:
                return fl + 1
            if fl % 2 == 0:
                return fl
            return fl + 1
        shift = 10 ** abs(ndigits)
        if ndigits > 0:
            return Fraction((self * shift).__round__(None), shift)
        return Fraction((self / shift).__round__(None) * shift)

    def limit_denominator(self, max_denominator=1000000):
        if max_denominator < 1:
            raise ValueError("max_denominator should be at least 1")
        if self.denominator <= max_denominator:
            return Fraction(self.numerator, self.denominator, True)
        p0 = 0
        q0 = 1
        p1 = 1
        q1 = 0
        n = self.numerator
        d = self.denominator
        while True:
            a = n // d
            q2 = q0 + a * q1
            if q2 > max_denominator:
                break
            t = p0 + a * p1
            p0 = p1
            q0 = q1
            p1 = t
            q1 = q2
            t = n - a * d
            n = d
            d = t
        k = (max_denominator - q0) // q1
        if 2 * d * (q0 + k * q1) <= self.denominator:
            return Fraction(p1, q1, True)
        return Fraction(p0 + k * p1, q0 + k * q1, True)

    # -- arithmetic ------------------------------------------------------------------------------
    def __add__(self, other):
        if isinstance(other, float):
            return float(self) + other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            return _ail_fr_add(self, o)
        raise TypeError("unsupported operand type(s) for +: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __radd__(self, other):
        if isinstance(other, float):
            return other + float(self)
        if isinstance(other, int):
            return _ail_fr_add(Fraction(other, 1, True), self)
        raise TypeError("unsupported operand type(s) for +: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __sub__(self, other):
        if isinstance(other, float):
            return float(self) - other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            return _ail_fr_sub(self, o)
        raise TypeError("unsupported operand type(s) for -: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rsub__(self, other):
        if isinstance(other, float):
            return other - float(self)
        if isinstance(other, int):
            return _ail_fr_sub(Fraction(other, 1, True), self)
        raise TypeError("unsupported operand type(s) for -: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __mul__(self, other):
        if isinstance(other, float):
            return float(self) * other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            return _ail_fr_mul(self, o)
        raise TypeError("unsupported operand type(s) for *: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rmul__(self, other):
        if isinstance(other, float):
            return other * float(self)
        if isinstance(other, int):
            return _ail_fr_mul(Fraction(other, 1, True), self)
        raise TypeError("unsupported operand type(s) for *: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __truediv__(self, other):
        if isinstance(other, float):
            return float(self) / other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            return _ail_fr_div(self, o)
        raise TypeError("unsupported operand type(s) for /: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rtruediv__(self, other):
        if isinstance(other, float):
            return other / float(self)
        if isinstance(other, int):
            return _ail_fr_div(Fraction(other, 1, True), self)
        raise TypeError("unsupported operand type(s) for /: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __floordiv__(self, other):
        if isinstance(other, float):
            return float(self) // other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            return (self.numerator * o.denominator) // (self.denominator * o.numerator)
        raise TypeError("unsupported operand type(s) for //: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rfloordiv__(self, other):
        if isinstance(other, float):
            return other // float(self)
        if isinstance(other, int):
            return (other * self.denominator) // self.numerator
        raise TypeError("unsupported operand type(s) for //: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __mod__(self, other):
        if isinstance(other, float):
            return float(self) % other
        if (isinstance(other, int) or isinstance(other, Fraction)):
            o = other
            if isinstance(other, int):
                o = Fraction(other, 1, True)
            da = self.denominator
            db = o.denominator
            return Fraction((self.numerator * db) % (o.numerator * da), da * db)
        raise TypeError("unsupported operand type(s) for %%: 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rmod__(self, other):
        if isinstance(other, float):
            return other % float(self)
        if isinstance(other, int):
            da = 1
            db = self.denominator
            return Fraction((other * db) % (self.numerator * da), da * db)
        raise TypeError("unsupported operand type(s) for %%: '%s' and 'Fraction'" % _ail_fr_tname(other))

    def __divmod__(self, other):
        return (self // other, self % other)

    def __rdivmod__(self, other):
        return (other // self, other % self)

    def __pow__(self, other):
        if isinstance(other, Fraction) and other.denominator == 1:
            other = other.numerator
        if isinstance(other, int):
            if other >= 0:
                return Fraction(self.numerator ** other, self.denominator ** other, True)
            if self.numerator > 0:
                return Fraction(self.denominator ** (-other), self.numerator ** (-other), True)
            if self.numerator == 0:
                raise ZeroDivisionError("Fraction(%s, 0)" % (self.denominator ** (-other)))
            return Fraction((-self.denominator) ** (-other), (-self.numerator) ** (-other), True)
        if isinstance(other, Fraction):
            return float(self) ** float(other)
        if isinstance(other, float):
            return float(self) ** other
        raise TypeError("unsupported operand type(s) for ** or pow(): 'Fraction' and '%s'" % _ail_fr_tname(other))

    def __rpow__(self, other):
        if self.denominator == 1 and self.numerator >= 0:
            return other ** self.numerator
        if isinstance(other, int):
            return Fraction(other, 1, True) ** self
        if self.denominator == 1:
            return other ** self.numerator
        return other ** float(self)

    # -- comparison ------------------------------------------------------------------------------
    def __eq__(self, other):
        if isinstance(other, Fraction):
            return self.numerator == other.numerator and self.denominator == other.denominator
        if isinstance(other, int):
            return self.denominator == 1 and self.numerator == other
        if isinstance(other, float):
            if other != other or other - other != 0.0:
                return False
            p = _ail_fr_float_parts(other)
            return self.numerator == p[0] and self.denominator == p[1]
        return False

    def __lt__(self, other):
        return _ail_fr_cmp(self, other) == -1

    def __gt__(self, other):
        return _ail_fr_cmp(self, other) == 1

    def __le__(self, other):
        c = _ail_fr_cmp(self, other)
        return c == -1 or c == 0

    def __ge__(self, other):
        c = _ail_fr_cmp(self, other)
        return c == 1 or c == 0


def _ail_fr_add(a, b):
    na = a.numerator
    da = a.denominator
    nb = b.numerator
    db = b.denominator
    g = _ail_fr_gcd(da, db)
    if g == 1:
        return Fraction(na * db + da * nb, da * db, True)
    s = da // g
    t = na * (db // g) + nb * s
    g2 = _ail_fr_gcd(t, g)
    if g2 == 1:
        return Fraction(t, s * db, True)
    return Fraction(t // g2, s * (db // g2), True)


def _ail_fr_sub(a, b):
    na = a.numerator
    da = a.denominator
    nb = b.numerator
    db = b.denominator
    g = _ail_fr_gcd(da, db)
    if g == 1:
        return Fraction(na * db - da * nb, da * db, True)
    s = da // g
    t = na * (db // g) - nb * s
    g2 = _ail_fr_gcd(t, g)
    if g2 == 1:
        return Fraction(t, s * db, True)
    return Fraction(t // g2, s * (db // g2), True)


def _ail_fr_mul(a, b):
    na = a.numerator
    da = a.denominator
    nb = b.numerator
    db = b.denominator
    g1 = _ail_fr_gcd(na, db)
    if g1 > 1:
        na = na // g1
        db = db // g1
    g2 = _ail_fr_gcd(nb, da)
    if g2 > 1:
        nb = nb // g2
        da = da // g2
    return Fraction(na * nb, db * da, True)


def _ail_fr_div(a, b):
    na = a.numerator
    da = a.denominator
    nb = b.numerator
    db = b.denominator
    if nb == 0:
        raise ZeroDivisionError("Fraction(%s, 0)" % da)
    g1 = _ail_fr_gcd(na, nb)
    if g1 > 1:
        na = na // g1
        nb = nb // g1
    g2 = _ail_fr_gcd(db, da)
    if g2 > 1:
        da = da // g2
        db = db // g2
    n = na * db
    d = nb * da
    if d < 0:
        n = -n
        d = -d
    return Fraction(n, d, True)


def _ail_fr_cmp(a, other) -> int:
    # -1, 0, 1; 2 when unordered (a NaN)
    if isinstance(other, Fraction):
        l = a.numerator * other.denominator
        r = a.denominator * other.numerator
    elif isinstance(other, int):
        l = a.numerator
        r = a.denominator * other
    elif isinstance(other, float):
        if other != other:
            return 2
        if other - other != 0.0:
            if other > 0.0:
                return -1
            return 1
        p = _ail_fr_float_parts(other)
        l = a.numerator * p[1]
        r = a.denominator * p[0]
    else:
        raise TypeError("'<' not supported between instances of 'Fraction' and '%s'" % _ail_fr_tname(other))
    if l < r:
        return -1
    if l > r:
        return 1
    return 0
