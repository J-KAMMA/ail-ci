# -*- coding: utf-8 -*-
# prelude_decimal.py -- `decimal.Decimal` as Python source (stdtop.py injects it).
#
# Plain Python in the subset the general path builds (classes with operator methods: dunderrt.py), and
# a module CPython imports as it stands, so the tests compare it with decimal.Decimal directly. The
# algorithms are those of CPython 3.12's _pydecimal.py, kept to what the C decimal module (libmpdec),
# which is what CPython 3.12 runs, gives: the coefficient is a Python int, the exponent an int, the kind
# 0 finite / 1 infinity / 2 quiet NaN / 3 signaling NaN. Context: one global context with prec, rounding,
# Emin, Emax, capitals and clamp; the traps are the default ones (InvalidOperation, DivisionByZero,
# Overflow) and cannot be changed; the flags are not kept. The pass in stdtop.py refuses by name what is
# not built (sqrt of nothing else, ln / exp / log10, fma, the Context methods, traps / flags, ...).


ROUND_UP = "ROUND_UP"
ROUND_DOWN = "ROUND_DOWN"
ROUND_CEILING = "ROUND_CEILING"
ROUND_FLOOR = "ROUND_FLOOR"
ROUND_HALF_UP = "ROUND_HALF_UP"
ROUND_HALF_DOWN = "ROUND_HALF_DOWN"
ROUND_HALF_EVEN = "ROUND_HALF_EVEN"
ROUND_05UP = "ROUND_05UP"

MAX_PREC = 999999999999999999
MAX_EMAX = 999999999999999999
MIN_EMIN = -999999999999999999
MIN_ETINY = -1999999999999999997


class DecimalException(Exception):
    pass


class InvalidOperation(DecimalException):
    pass


class ConversionSyntax(InvalidOperation):
    pass


class DivisionImpossible(InvalidOperation):
    pass


class DivisionUndefined(InvalidOperation):
    pass


class InvalidContext(InvalidOperation):
    pass


class DivisionByZero(ZeroDivisionError):
    pass


class Overflow(DecimalException):
    pass


class Inexact(DecimalException):
    pass


class Rounded(DecimalException):
    pass


class Subnormal(DecimalException):
    pass


class Underflow(DecimalException):
    pass


class Clamped(DecimalException):
    pass


class FloatOperation(DecimalException):
    pass


def _ail_dec_invalid(cond: str):
    raise InvalidOperation("[<class 'decimal.%s'>]" % cond)


def _ail_dec_tname(x) -> str:
    if x is None:
        return "NoneType"
    return type(x).__name__


def _ail_dec_binerr(op: str, reflected: bool, other) -> str:
    # the TypeError text of `Decimal op other` (reflected: `other op Decimal`) for an operand that is no number
    tn = _ail_dec_tname(other)
    seq = isinstance(other, str) or isinstance(other, list) or isinstance(other, tuple) or isinstance(other, bytes)
    if op == "*" and seq:
        return "can't multiply sequence by non-int of type 'decimal.Decimal'"
    if op == "+" and seq and reflected:
        return 'can only concatenate %s (not "decimal.Decimal") to %s' % (tn, tn)
    if reflected:
        return "unsupported operand type(s) for %s: '%s' and 'decimal.Decimal'" % (op, tn)
    return "unsupported operand type(s) for %s: 'decimal.Decimal' and '%s'" % (op, tn)


def _ail_dec_num(x):
    # an argument of a float function of math: float(Decimal), anything else as it is
    if isinstance(x, Decimal):
        return float(x)
    return x


def _ail_dec_p10(k: int) -> int:
    return 10 ** k


def _ail_dec_nd(c: int) -> int:
    # the number of decimal digits of c >= 0 (1 for zero); no int <-> str conversion of a long number, which has a
    # 4300-digit limit in CPython and in the compiled runtime
    if c < 1000000000000000000:
        return len(str(c))
    d = (c.bit_length() * 30103) // 100000
    if d < 1:
        d = 1
    while 10 ** d <= c:
        d = d + 1
    while d > 1 and 10 ** (d - 1) > c:
        d = d - 1
    return d


def _ail_dec_digs(c: int) -> str:
    # str(c) for c >= 0 in chunks of 1000 digits
    if c.bit_length() < 12000:
        return str(c)
    big = _ail_dec_p10(1000)
    parts = []
    while c >= big:
        qr = divmod(c, big)
        parts.append(str(qr[1]).zfill(1000))
        c = qr[0]
    parts.append(str(c))
    parts.reverse()
    return "".join(parts)


# ---------------------------------------------------------------------------------------------------------------
# the context
# ---------------------------------------------------------------------------------------------------------------
class Context:
    def __init__(self, prec=None, rounding=None, Emin=None, Emax=None, capitals=None, clamp=None, flags=None,
                 traps=None):
        self.prec = 28
        self.rounding = "ROUND_HALF_EVEN"
        self.Emin = -999999
        self.Emax = 999999
        self.capitals = 1
        self.clamp = 0
        if prec is not None:
            _ail_dec_set(self, "prec", prec)
        if rounding is not None:
            _ail_dec_set(self, "rounding", rounding)
        if Emin is not None:
            _ail_dec_set(self, "Emin", Emin)
        if Emax is not None:
            _ail_dec_set(self, "Emax", Emax)
        if capitals is not None:
            _ail_dec_set(self, "capitals", capitals)
        if clamp is not None:
            _ail_dec_set(self, "clamp", clamp)

    def copy(self):
        c = Context()
        c.prec = self.prec
        c.rounding = self.rounding
        c.Emin = self.Emin
        c.Emax = self.Emax
        c.capitals = self.capitals
        c.clamp = self.clamp
        return c

    def Etiny(self) -> int:
        return self.Emin - self.prec + 1

    def Etop(self) -> int:
        return self.Emax - self.prec + 1

    def create_decimal(self, num="0"):
        d = Decimal(num)
        return _ail_dec_pos_nr(d, self)

    def __repr__(self) -> str:
        raise RuntimeError("repr of a decimal context is not built (the flags are not kept)")


def _ail_dec_set(ctx, name: str, value):
    # the checks of the C module for `ctx.name = value`
    if name == "rounding":
        ok = (isinstance(value, str) and (value == "ROUND_UP" or value == "ROUND_DOWN" or value == "ROUND_CEILING"
                                          or value == "ROUND_FLOOR" or value == "ROUND_HALF_UP"
                                          or value == "ROUND_HALF_DOWN" or value == "ROUND_HALF_EVEN"
                                          or value == "ROUND_05UP"))
        if not ok:
            raise TypeError("valid values for rounding are:\n  [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN,\n"
                            "   ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN,\n   ROUND_05UP]")
        ctx.rounding = value
        return value
    if isinstance(value, bool):
        value = int(value)
    elif not isinstance(value, int):
        raise TypeError("an integer is required")
    magnitude = value
    if value < 0:
        magnitude = -value - 1
    if magnitude.bit_length() > 63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if name == "prec":
        if value < 1 or value > 999999999999999999:
            raise ValueError("valid range for prec is [1, MAX_PREC]")
        ctx.prec = value
    elif name == "Emax":
        if value < 0 or value > 999999999999999999:
            raise ValueError("valid range for Emax is [0, MAX_EMAX]")
        ctx.Emax = value
    elif name == "Emin":
        if value > 0 or value < -999999999999999999:
            raise ValueError("valid range for Emin is [MIN_EMIN, 0]")
        ctx.Emin = value
    elif name == "capitals":
        if value != 0 and value != 1:
            raise ValueError("valid values for capitals are 0 or 1")
        ctx.capitals = value
    else:
        if value != 0 and value != 1:
            raise ValueError("valid values for clamp are 0 or 1")
        ctx.clamp = value
    return value


_ail_dec_ctx = Context()


def getcontext():
    return _ail_dec_ctx


def setcontext(c):
    global _ail_dec_ctx
    if not isinstance(c, Context):
        raise TypeError("argument must be a context")
    _ail_dec_ctx = c.copy()


class _ail_dec_Local:
    def __init__(self, c):
        self.new = c
        self.saved = None

    def __enter__(self):
        global _ail_dec_ctx
        self.saved = _ail_dec_ctx
        _ail_dec_ctx = self.new
        return self.new

    def __exit__(self, a, b, c):
        global _ail_dec_ctx
        _ail_dec_ctx = self.saved
        return False


def localcontext(ctx=None, prec=None, rounding=None, Emin=None, Emax=None, capitals=None, clamp=None):
    if ctx is None:
        c = _ail_dec_ctx.copy()
    else:
        if not isinstance(ctx, Context):
            raise TypeError("optional argument must be a context")
        c = ctx.copy()
    if prec is not None:
        _ail_dec_set(c, "prec", prec)
    if rounding is not None:
        _ail_dec_set(c, "rounding", rounding)
    if Emin is not None:
        _ail_dec_set(c, "Emin", Emin)
    if Emax is not None:
        _ail_dec_set(c, "Emax", Emax)
    if capitals is not None:
        _ail_dec_set(c, "capitals", capitals)
    if clamp is not None:
        _ail_dec_set(c, "clamp", clamp)
    return _ail_dec_Local(c)


# ---------------------------------------------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------------------------------------------
class Decimal:
    def __init__(self, value="0", context=None):
        self._s = 0
        self._c = 0
        self._e = 0
        self._k = 0
        if isinstance(value, str):
            r = _ail_dec_parse(value)
            if r[3] == 4:
                if r[0] == 1:
                    raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
                raise InvalidOperation("[<class 'decimal.ConversionSyntax'>]")
            self._s = r[0]
            self._c = r[1]
            self._e = r[2]
            self._k = r[3]
        elif isinstance(value, bool):
            if value:
                self._c = 1
        elif isinstance(value, int):
            if value < 0:
                self._s = 1
                self._c = -value
            else:
                self._c = value
        elif isinstance(value, Decimal):
            self._s = value._s
            self._c = value._c
            self._e = value._e
            self._k = value._k
        elif isinstance(value, float):
            r = _ail_dec_from_float(value)
            self._s = r[0]
            self._c = r[1]
            self._e = r[2]
            self._k = r[3]
        elif isinstance(value, tuple) or isinstance(value, list):
            r = _ail_dec_from_tuple(value)
            self._s = r[0]
            self._c = r[1]
            self._e = r[2]
            self._k = r[3]
        else:
            raise TypeError("conversion from %s to Decimal is not supported" % _ail_dec_tname(value))

    def __repr__(self) -> str:
        return "Decimal('%s')" % _ail_dec_str(self, False)

    def __str__(self) -> str:
        return _ail_dec_str(self, False)

    def to_eng_string(self, context=None) -> str:
        return _ail_dec_str(self, True)

    def __bool__(self) -> bool:
        return self._k != 0 or self._c != 0

    def __hash__(self):
        return _ail_dec_hash(self)

    def __neg__(self):
        return _ail_dec_neg(self, _ail_dec_ctx)

    def __pos__(self):
        return _ail_dec_pos(self, _ail_dec_ctx)

    def __abs__(self):
        if self._s == 1:
            return _ail_dec_neg(self, _ail_dec_ctx)
        return _ail_dec_pos(self, _ail_dec_ctx)

    def __float__(self) -> float:
        if self._k == 3:
            raise ValueError("cannot convert signaling NaN to float")
        if self._k == 2:
            if self._s == 1:
                return -float("nan")
            return float("nan")
        return float(_ail_dec_str(self, False))

    def __int__(self):
        return _ail_dec_toint(self)

    def __trunc__(self):
        return _ail_dec_toint(self)

    def __floor__(self):
        return _ail_dec_round_to_int(self, "ROUND_FLOOR")

    def __ceil__(self):
        return _ail_dec_round_to_int(self, "ROUND_CEILING")

    def __round__(self, n=None):
        if n is not None:
            if isinstance(n, bool) or not isinstance(n, int):
                raise TypeError("optional arg must be an integer")
            return _ail_dec_quantize(self, _ail_dec_mk(0, 1, -n, 0), _ail_dec_ctx.rounding, _ail_dec_ctx)
        return _ail_dec_round_to_int(self, "ROUND_HALF_EVEN")

    def conjugate(self):
        return self

    def radix(self):
        return Decimal(10)

    def is_nan(self) -> bool:
        return self._k >= 2

    def is_qnan(self) -> bool:
        return self._k == 2

    def is_snan(self) -> bool:
        return self._k == 3

    def is_infinite(self) -> bool:
        return self._k == 1

    def is_finite(self) -> bool:
        return self._k == 0

    def is_signed(self) -> bool:
        return self._s == 1

    def is_zero(self) -> bool:
        return self._k == 0 and self._c == 0

    def is_normal(self, context=None) -> bool:
        if self._k != 0 or self._c == 0:
            return False
        return _ail_dec_adjusted(self) >= _ail_dec_ctx.Emin

    def is_subnormal(self, context=None) -> bool:
        if self._k != 0 or self._c == 0:
            return False
        return _ail_dec_adjusted(self) < _ail_dec_ctx.Emin

    def adjusted(self) -> int:
        return _ail_dec_adjusted(self)

    def copy_abs(self):
        return _ail_dec_mk(0, self._c, self._e, self._k)

    def copy_negate(self):
        return _ail_dec_mk(1 - self._s, self._c, self._e, self._k)

    def copy_sign(self, other):
        o = _ail_dec_conv_strict(other)
        return _ail_dec_mk(o._s, self._c, self._e, self._k)

    def as_integer_ratio(self):
        if self._k != 0:
            if self._k >= 2:
                raise ValueError("cannot convert NaN to integer ratio")
            raise OverflowError("cannot convert Infinity to integer ratio")
        if self._c == 0:
            return (0, 1)
        n = self._c
        d = 1
        if self._e >= 0:
            n = n * _ail_dec_p10(self._e)
        else:
            d = _ail_dec_p10(-self._e)
            g = _ail_dec_gcd(n, d)
            n = n // g
            d = d // g
        if self._s == 1:
            n = -n
        return (n, d)

    def same_quantum(self, other) -> bool:
        o = _ail_dec_conv_strict(other)
        if self._k != 0 or o._k != 0:
            return (self._k >= 2 and o._k >= 2) or (self._k == 1 and o._k == 1)
        return self._e == o._e

    def normalize(self, context=None):
        return _ail_dec_normalize(self, _ail_dec_ctx)

    def quantize(self, exp, rounding=None, context=None):
        e = _ail_dec_conv_strict(exp)
        c = _ail_dec_ctx
        m = c.rounding
        if rounding is not None:
            m = _ail_dec_mode(rounding)
        return _ail_dec_quantize(self, e, m, c)

    def to_integral_value(self, rounding=None, context=None):
        c = _ail_dec_ctx
        m = c.rounding
        if rounding is not None:
            m = _ail_dec_mode(rounding)
        return _ail_dec_integral(self, m, c, False)

    def to_integral(self, rounding=None, context=None):
        c = _ail_dec_ctx
        m = c.rounding
        if rounding is not None:
            m = _ail_dec_mode(rounding)
        return _ail_dec_integral(self, m, c, False)

    def to_integral_exact(self, rounding=None, context=None):
        c = _ail_dec_ctx
        m = c.rounding
        if rounding is not None:
            m = _ail_dec_mode(rounding)
        return _ail_dec_integral(self, m, c, True)

    def sqrt(self, context=None):
        return _ail_dec_sqrt(self, _ail_dec_ctx)

    def compare(self, other, context=None):
        o = _ail_dec_conv_strict(other)
        if self._k != 0 or o._k != 0:
            r = _ail_dec_nan2(self, o, _ail_dec_ctx)
            if r is not None:
                return r
        return Decimal(_ail_dec_cmp(self, o))

    def max(self, other, context=None):
        o = _ail_dec_conv_strict(other)
        return _ail_dec_maxmin(self, o, _ail_dec_ctx, True)

    def min(self, other, context=None):
        o = _ail_dec_conv_strict(other)
        return _ail_dec_maxmin(self, o, _ail_dec_ctx, False)

    # -- arithmetic ------------------------------------------------------------------------------
    def __add__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("+", False, other))
        return _ail_dec_add(self, o, _ail_dec_ctx)

    def __radd__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("+", True, other))
        return _ail_dec_add(o, self, _ail_dec_ctx)

    def __sub__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("-", False, other))
        return _ail_dec_sub(self, o, _ail_dec_ctx)

    def __rsub__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("-", True, other))
        return _ail_dec_sub(o, self, _ail_dec_ctx)

    def __mul__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("*", False, other))
        return _ail_dec_mul(self, o, _ail_dec_ctx)

    def __rmul__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("*", True, other))
        return _ail_dec_mul(o, self, _ail_dec_ctx)

    def __truediv__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("/", False, other))
        return _ail_dec_div(self, o, _ail_dec_ctx)

    def __rtruediv__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("/", True, other))
        return _ail_dec_div(o, self, _ail_dec_ctx)

    def __floordiv__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("//", False, other))
        return _ail_dec_floordiv(self, o, _ail_dec_ctx)

    def __rfloordiv__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("//", True, other))
        return _ail_dec_floordiv(o, self, _ail_dec_ctx)

    def __mod__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("%", False, other))
        return _ail_dec_mod(self, o, _ail_dec_ctx)

    def __rmod__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("%", True, other))
        return _ail_dec_mod(o, self, _ail_dec_ctx)

    def __divmod__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("divmod()", False, other))
        return _ail_dec_divmod(self, o, _ail_dec_ctx)

    def __rdivmod__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("divmod()", True, other))
        return _ail_dec_divmod(o, self, _ail_dec_ctx)

    def __pow__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("** or pow()", False, other))
        return _ail_dec_pow(self, o, _ail_dec_ctx)

    def __rpow__(self, other):
        o = _ail_dec_conv(other)
        if o is None:
            raise TypeError(_ail_dec_binerr("** or pow()", True, other))
        return _ail_dec_pow(o, self, _ail_dec_ctx)

    # -- comparison ------------------------------------------------------------------------------
    def __eq__(self, other):
        o = _ail_dec_conv_cmp(other)
        if o is None:
            return False
        if self._k >= 2 or o._k >= 2:
            if self._k == 3 or o._k == 3:
                _ail_dec_invalid("InvalidOperation")
            return False
        return _ail_dec_cmp(self, o) == 0

    def __lt__(self, other):
        o = _ail_dec_conv_cmp(other)
        if o is None:
            raise TypeError("'<' not supported between instances of 'decimal.Decimal' and '%s'"
                            % _ail_dec_tname(other))
        if self._k >= 2 or o._k >= 2:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_cmp(self, o) < 0

    def __le__(self, other):
        o = _ail_dec_conv_cmp(other)
        if o is None:
            raise TypeError("'<=' not supported between instances of 'decimal.Decimal' and '%s'"
                            % _ail_dec_tname(other))
        if self._k >= 2 or o._k >= 2:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_cmp(self, o) <= 0

    def __gt__(self, other):
        o = _ail_dec_conv_cmp(other)
        if o is None:
            raise TypeError("'>' not supported between instances of 'decimal.Decimal' and '%s'"
                            % _ail_dec_tname(other))
        if self._k >= 2 or o._k >= 2:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_cmp(self, o) > 0

    def __ge__(self, other):
        o = _ail_dec_conv_cmp(other)
        if o is None:
            raise TypeError("'>=' not supported between instances of 'decimal.Decimal' and '%s'"
                            % _ail_dec_tname(other))
        if self._k >= 2 or o._k >= 2:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_cmp(self, o) >= 0

    def __format__(self, spec):
        return _ail_dec_format(self, spec)


def _ail_dec_mk(s: int, c: int, e: int, k: int):
    d = Decimal(0)
    d._s = s
    d._c = c
    d._e = e
    d._k = k
    return d


def _ail_dec_from_float_fn(f):
    # Decimal.from_float(f)
    if isinstance(f, bool) or isinstance(f, int) or isinstance(f, float):
        return Decimal(f)
    raise TypeError("argument must be int or float.")


def _ail_dec_gcd(a: int, b: int) -> int:
    while b != 0:
        t = a % b
        a = b
        b = t
    return a


def _ail_dec_mode(m) -> str:
    ok = (isinstance(m, str) and (m == "ROUND_UP" or m == "ROUND_DOWN" or m == "ROUND_CEILING" or m == "ROUND_FLOOR"
                                  or m == "ROUND_HALF_UP" or m == "ROUND_HALF_DOWN" or m == "ROUND_HALF_EVEN"
                                  or m == "ROUND_05UP"))
    if not ok:
        raise TypeError("valid values for rounding are:\n  [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN,\n"
                        "   ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN,\n   ROUND_05UP]")
    return m


def _ail_dec_digit(ch: str) -> int:
    # the value of a decimal digit character (ASCII or any Unicode decimal digit), -1 when it is none
    if "0" <= ch <= "9":
        return ord(ch) - 48
    if ch.isdecimal():
        return int(ch)
    return -1


def _ail_dec_digits(s: str, i: int) -> int:
    # the end of the run of decimal digits that starts at i
    n = len(s)
    j = i
    while j < n and _ail_dec_digit(s[j]) >= 0:
        j = j + 1
    return j


def _ail_dec_int(s: str) -> int:
    # the int of a string of decimal digit characters (ASCII or Unicode), in chunks of 1000 digits
    n = len(s)
    if n < 1000 and s.isascii():
        if n == 0:
            return 0
        return int(s)
    v = 0
    i = 0
    while i < n:
        chunk = s[i:i + 1000]
        if chunk.isascii():
            w = int(chunk)
        else:
            w = 0
            for ch in chunk:
                w = w * 10 + _ail_dec_digit(ch)
        v = v * _ail_dec_p10(len(chunk)) + w
        i = i + 1000
    return v


def _ail_dec_parse(text: str) -> list[int]:
    # [sign, coefficient, exponent, kind]; kind 4 = not a number (sign 1: the exponent is out of range)
    s = text.strip().replace("_", "")
    n = len(s)
    i = 0
    sign = 0
    if i < n and (s[i] == "+" or s[i] == "-"):
        if s[i] == "-":
            sign = 1
        i = i + 1
    rest = s[i:].lower()
    if rest == "inf" or rest == "infinity":
        return [sign, 0, 0, 1]
    kind = 0
    pay = ""
    if rest.startswith("snan"):
        kind = 3
        pay = rest[4:]
    elif rest.startswith("nan"):
        kind = 2
        pay = rest[3:]
    if kind != 0:
        if _ail_dec_digits(pay, 0) != len(pay):
            return [0, 0, 0, 4]
        return [sign, _ail_dec_int(pay), 0, kind]
    j = _ail_dec_digits(s, i)
    ip = s[i:j]
    fp = ""
    if j < n and s[j] == ".":
        k = _ail_dec_digits(s, j + 1)
        fp = s[j + 1:k]
        j = k
    if ip == "" and fp == "":
        return [0, 0, 0, 4]
    ex = 0
    if j < n and (s[j] == "e" or s[j] == "E"):
        k = j + 1
        eneg = False
        if k < n and (s[k] == "+" or s[k] == "-"):
            eneg = s[k] == "-"
            k = k + 1
        m = _ail_dec_digits(s, k)
        if m == k:
            return [0, 0, 0, 4]
        ex = _ail_dec_int(s[k:m])
        if eneg:
            ex = -ex
        j = m
    if j != n:
        return [0, 0, 0, 4]
    ex = ex - len(fp)
    if ex > 999999999999999999 or ex < -999999999999999999:
        return [1, 0, 0, 4]
    return [sign, _ail_dec_int(ip + fp), ex, 0]


def _ail_dec_from_float(f: float) -> list[int]:
    if f != f:
        return [0, 0, 0, 2]
    if f - f != 0.0:
        if f > 0.0:
            return [0, 0, 0, 1]
        return [1, 0, 0, 1]
    sign = 0
    if f < 0.0 or (f == 0.0 and str(f).startswith("-")):
        sign = 1
    if f < 0.0:
        f = -f
    k = 0
    while f != float(int(f)):
        f = f * 2.0
        k = k + 1
    n = int(f)
    if k == 0:
        return [sign, n, 0, 0]
    return [sign, n * (5 ** k), -k, 0]


def _ail_dec_from_tuple(v) -> list[int]:
    if len(v) != 3:
        raise ValueError("argument must be a sequence of length 3")
    sg = v[0]
    if isinstance(sg, bool) or not isinstance(sg, int) or (sg != 0 and sg != 1):
        raise ValueError("sign must be an integer with the value 0 or 1")
    ex = v[2]
    digs = v[1]
    if not (isinstance(digs, tuple) or isinstance(digs, list)):
        raise ValueError("coefficient must be a tuple of digits")
    if isinstance(ex, str):
        if ex == "F":
            return [sg, 0, 0, 1]
        if ex != "n" and ex != "N":
            raise ValueError("string argument in the third position must be 'F', 'n' or 'N'")
    elif isinstance(ex, bool) or not isinstance(ex, int):
        raise ValueError("exponent must be an integer")
    c = 0
    for dg in digs:
        if isinstance(dg, bool) or not isinstance(dg, int) or dg < 0 or dg > 9:
            raise ValueError("coefficient must be a tuple of digits")
        c = c * 10 + dg
    if isinstance(ex, str):
        if ex == "n":
            return [sg, c, 0, 2]
        return [sg, c, 0, 3]
    if ex > 999999999999999999 or ex < -999999999999999999:
        raise ValueError("exponent must be an integer")
    return [sg, c, ex, 0]


def _ail_dec_conv(x):
    # the Decimal an operand stands for in arithmetic, None for an operand of another type
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    return None


def _ail_dec_conv_strict(x):
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    raise TypeError("conversion from %s to Decimal is not supported" % _ail_dec_tname(x))


def _ail_dec_conv_cmp(x):
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        return Decimal(x)
    return None


# ---------------------------------------------------------------------------------------------------------------
# rounding
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_inc(q: int, r: int, k: int, sign: int, mode: str) -> int:
    # 1 when the kept part q is to be incremented: r is the dropped part, 0 <= r < 10**k
    if r == 0:
        return 0
    if mode == "ROUND_DOWN":
        return 0
    if mode == "ROUND_UP":
        return 1
    half = 5 * _ail_dec_p10(k - 1)
    if mode == "ROUND_HALF_UP":
        if r >= half:
            return 1
        return 0
    if mode == "ROUND_HALF_DOWN":
        if r > half:
            return 1
        return 0
    if mode == "ROUND_HALF_EVEN":
        if r > half or (r == half and q % 2 == 1):
            return 1
        return 0
    if mode == "ROUND_CEILING":
        if sign == 0:
            return 1
        return 0
    if mode == "ROUND_FLOOR":
        if sign == 1:
            return 1
        return 0
    d = q % 10
    if d == 0 or d == 5:
        return 1
    return 0


def _ail_dec_drop(c: int, k: int, sign: int, mode: str) -> int:
    # the coefficient c without its k lowest digits (k > 0), rounded by the mode
    nd = _ail_dec_nd(c)
    if k > nd:
        return _ail_dec_inc(0, 1, 1, sign, mode)
    p = _ail_dec_p10(k)
    q = c // p
    r = c % p
    return q + _ail_dec_inc(q, r, k, sign, mode)


def _ail_dec_rescale(d, exp: int, mode: str):
    # a finite d at the exponent exp, padded with zeros or rounded
    if d._k != 0:
        return d
    if d._c == 0:
        return _ail_dec_mk(d._s, 0, exp, 0)
    if d._e >= exp:
        return _ail_dec_mk(d._s, d._c * _ail_dec_p10(d._e - exp), exp, 0)
    return _ail_dec_mk(d._s, _ail_dec_drop(d._c, exp - d._e, d._s, mode), exp, 0)


def _ail_dec_fix(s: int, c: int, e: int, ctx):
    # a finite value rounded into the context: precision, then the exponent limits
    prec = ctx.prec
    etiny = ctx.Emin - prec + 1
    etop = ctx.Emax - prec + 1
    if c == 0:
        top = ctx.Emax
        if ctx.clamp == 1:
            top = etop
        ne = e
        if ne < etiny:
            ne = etiny
        if ne > top:
            ne = top
        return _ail_dec_mk(s, 0, ne, 0)
    nd = _ail_dec_nd(c)
    exp_min = nd + e - prec
    if exp_min > etop:
        raise Overflow("[<class 'decimal.Overflow'>]")
    if exp_min < etiny:
        exp_min = etiny
    if e < exp_min:
        k = exp_min - e
        c2 = _ail_dec_drop(c, k, s, ctx.rounding)
        if _ail_dec_nd(c2) > prec:
            c2 = c2 // 10
            exp_min = exp_min + 1
        if exp_min > etop:
            raise Overflow("[<class 'decimal.Overflow'>]")
        return _ail_dec_mk(s, c2, exp_min, 0)
    if ctx.clamp == 1 and e > etop:
        return _ail_dec_mk(s, c * _ail_dec_p10(e - etop), etop, 0)
    return _ail_dec_mk(s, c, e, 0)


def _ail_dec_fix_nan(d, ctx):
    pay = d._c
    mx = ctx.prec - ctx.clamp
    if _ail_dec_nd(pay) > mx and pay != 0:
        pay = pay % _ail_dec_p10(mx)
    return _ail_dec_mk(d._s, pay, 0, d._k)


def _ail_dec_nan2(a, b, ctx):
    # the NaN result of an operation with a NaN operand (a signaling one raises), None when there is none
    if a._k >= 2 or b._k >= 2:
        if a._k == 3 or b._k == 3:
            _ail_dec_invalid("InvalidOperation")
        if a._k == 2:
            return _ail_dec_fix_nan(a, ctx)
        return _ail_dec_fix_nan(b, ctx)
    return None


def _ail_dec_nan1(a, ctx):
    if a._k >= 2:
        if a._k == 3:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_fix_nan(a, ctx)
    return None


def _ail_dec_inf(sign: int):
    return _ail_dec_mk(sign, 0, 0, 1)


def _ail_dec_adjusted(d) -> int:
    if d._k != 0:
        return 0
    return d._e + _ail_dec_nd(d._c) - 1


# ---------------------------------------------------------------------------------------------------------------
# str, hash, conversions
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_str(d, eng: bool) -> str:
    sign = ""
    if d._s == 1:
        sign = "-"
    if d._k == 1:
        return sign + "Infinity"
    if d._k >= 2:
        pay = ""
        if d._c != 0:
            pay = _ail_dec_digs(d._c)
        if d._k == 2:
            return sign + "NaN" + pay
        return sign + "sNaN" + pay
    digs = _ail_dec_digs(d._c)
    nd = len(digs)
    leftdigits = d._e + nd
    if d._e <= 0 and leftdigits > -6:
        dotplace = leftdigits
    elif not eng:
        dotplace = 1
    elif d._c == 0:
        dotplace = (leftdigits + 1) % 3 - 1
    else:
        dotplace = (leftdigits - 1) % 3 + 1
    if dotplace <= 0:
        intpart = "0"
        fracpart = "." + "0" * (-dotplace) + digs
    elif dotplace >= nd:
        intpart = digs + "0" * (dotplace - nd)
        fracpart = ""
    else:
        intpart = digs[:dotplace]
        fracpart = "." + digs[dotplace:]
    exp = ""
    if leftdigits != dotplace:
        ex = leftdigits - dotplace
        es = str(ex)
        if ex >= 0:
            es = "+" + es
        if _ail_dec_ctx.capitals == 1:
            exp = "E" + es
        else:
            exp = "e" + es
    return sign + intpart + fracpart + exp


def _ail_dec_hash(d):
    if d._k == 3:
        raise TypeError("Cannot hash a signaling NaN value.")
    if d._k == 2:
        return 0
    if d._k == 1:
        if d._s == 1:
            return -314159
        return 314159
    mod = 2305843009213693951
    if d._e >= 0:
        eh = pow(10, d._e, mod)
    else:
        eh = pow(_ail_dec_inv10(), -d._e, mod)
    h = d._c * eh % mod
    if d._s == 1:
        h = -h
    if h == -1:
        return -2
    return h


def _ail_dec_inv10() -> int:
    # the inverse of 10 modulo 2**61 - 1
    return 2075258708292324556


def _ail_dec_toint(d):
    if d._k >= 2:
        raise ValueError("cannot convert NaN to integer")
    if d._k == 1:
        raise OverflowError("cannot convert Infinity to integer")
    if d._e >= 0:
        v = d._c * _ail_dec_p10(d._e)
    else:
        v = d._c // _ail_dec_p10(-d._e)
    if d._s == 1:
        return -v
    return v


def _ail_dec_round_to_int(d, mode: str):
    if d._k >= 2:
        raise ValueError("cannot convert NaN to integer")
    if d._k == 1:
        raise OverflowError("cannot convert Infinity to integer")
    r = _ail_dec_rescale(d, 0, mode)
    if r._s == 1:
        return -r._c
    return r._c


# ---------------------------------------------------------------------------------------------------------------
# unary
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_neg(d, ctx):
    r = _ail_dec_nan1(d, ctx)
    if r is not None:
        return r
    if d._k == 1:
        return _ail_dec_mk(1 - d._s, 0, 0, 1)
    if d._c == 0 and ctx.rounding != "ROUND_FLOOR":
        return _ail_dec_fix(0, 0, d._e, ctx)
    return _ail_dec_fix(1 - d._s, d._c, d._e, ctx)


def _ail_dec_pos(d, ctx):
    r = _ail_dec_nan1(d, ctx)
    if r is not None:
        return r
    if d._k == 1:
        return d
    if d._c == 0 and ctx.rounding != "ROUND_FLOOR":
        return _ail_dec_fix(0, 0, d._e, ctx)
    return _ail_dec_fix(d._s, d._c, d._e, ctx)


def _ail_dec_normalize(d, ctx):
    r = _ail_dec_nan1(d, ctx)
    if r is not None:
        return r
    if d._k == 1:
        return d
    f = _ail_dec_fix(d._s, d._c, d._e, ctx)
    if f._c == 0:
        return _ail_dec_mk(f._s, 0, 0, 0)
    exp_max = ctx.Emax
    if ctx.clamp == 1:
        exp_max = ctx.Emax - ctx.prec + 1
    c = f._c
    e = f._e
    while c % 10 == 0 and e < exp_max:
        c = c // 10
        e = e + 1
    return _ail_dec_mk(f._s, c, e, 0)


def _ail_dec_integral(d, mode: str, ctx, exact: bool):
    if d._k != 0:
        r = _ail_dec_nan1(d, ctx)
        if r is not None:
            return r
        return d
    if d._e >= 0:
        return d
    if exact and d._c == 0:
        return _ail_dec_mk(d._s, 0, 0, 0)
    return _ail_dec_rescale(d, 0, mode)


def _ail_dec_quantize(d, q, mode: str, ctx):
    if d._k != 0 or q._k != 0:
        r = _ail_dec_nan2(d, q, ctx)
        if r is not None:
            return r
        if q._k == 1 or d._k == 1:
            if q._k == 1 and d._k == 1:
                return d
            _ail_dec_invalid("InvalidOperation")
    etiny = ctx.Emin - ctx.prec + 1
    if q._e < etiny or q._e > ctx.Emax:
        _ail_dec_invalid("InvalidOperation")
    if d._c == 0:
        return _ail_dec_fix(d._s, 0, q._e, ctx)
    adj = _ail_dec_adjusted(d)
    if adj > ctx.Emax:
        _ail_dec_invalid("InvalidOperation")
    if adj - q._e + 1 > ctx.prec:
        _ail_dec_invalid("InvalidOperation")
    a = _ail_dec_rescale(d, q._e, mode)
    if _ail_dec_adjusted(a) > ctx.Emax:
        _ail_dec_invalid("InvalidOperation")
    if _ail_dec_nd(a._c) > ctx.prec:
        _ail_dec_invalid("InvalidOperation")
    return _ail_dec_fix(a._s, a._c, a._e, ctx)


def _ail_dec_sqrt(d, ctx):
    if d._k != 0:
        r = _ail_dec_nan1(d, ctx)
        if r is not None:
            return r
        if d._k == 1 and d._s == 0:
            return d
    if d._k == 0 and d._c == 0:
        return _ail_dec_fix(d._s, 0, d._e // 2, ctx)
    if d._s == 1:
        _ail_dec_invalid("InvalidOperation")
    prec = ctx.prec + 1
    e = d._e >> 1
    nd = _ail_dec_nd(d._c)
    if d._e & 1 == 1:
        c = d._c * 10
        l = (nd >> 1) + 1
    else:
        c = d._c
        l = (nd + 1) >> 1
    shift = prec - l
    exact = True
    if shift >= 0:
        c = c * _ail_dec_p10(2 * shift)
    else:
        p = _ail_dec_p10(-2 * shift)
        rem = c % p
        c = c // p
        exact = rem == 0
    e = e - shift
    n = _ail_dec_p10(prec)
    while True:
        q = c // n
        if n <= q:
            break
        n = (n + q) >> 1
    exact = exact and n * n == c
    if exact:
        if shift >= 0:
            n = n // _ail_dec_p10(shift)
        else:
            n = n * _ail_dec_p10(-shift)
        e = e + shift
    else:
        if n % 5 == 0:
            n = n + 1
    c2 = ctx.copy()
    c2.rounding = "ROUND_HALF_EVEN"
    return _ail_dec_fix(0, n, e, c2)


# ---------------------------------------------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_cmp(a, b) -> int:
    # -1, 0, 1 for two numbers (no NaN)
    if a._k != 0 or b._k != 0:
        ai = 0
        bi = 0
        if a._k == 1:
            ai = 1 - 2 * a._s
        if b._k == 1:
            bi = 1 - 2 * b._s
        if ai == bi:
            return 0
        if ai < bi:
            return -1
        return 1
    if a._c == 0:
        if b._c == 0:
            return 0
        if b._s == 1:
            return 1
        return -1
    if b._c == 0:
        if a._s == 1:
            return -1
        return 1
    if a._s != b._s:
        if a._s == 1:
            return -1
        return 1
    aa = _ail_dec_adjusted(a)
    ba = _ail_dec_adjusted(b)
    r = 0
    if aa == ba:
        if a._e >= b._e:
            x = a._c * _ail_dec_p10(a._e - b._e)
            y = b._c
        else:
            x = a._c
            y = b._c * _ail_dec_p10(b._e - a._e)
        if x < y:
            r = -1
        elif x > y:
            r = 1
    elif aa > ba:
        r = 1
    else:
        r = -1
    if a._s == 1:
        return -r
    return r


def _ail_dec_total_finite(a, b) -> int:
    # the total order of two finite numbers that compare equal: by sign, then by exponent
    if a._s == 1 and b._s == 0:
        return -1
    if a._s == 0 and b._s == 1:
        return 1
    if a._e < b._e:
        if a._s == 1:
            return 1
        return -1
    if a._e > b._e:
        if a._s == 1:
            return -1
        return 1
    return 0


def _ail_dec_maxmin(a, b, ctx, want_max: bool):
    if a._k != 0 or b._k != 0:
        sn = 0
        on = 0
        if a._k >= 2:
            sn = a._k - 1
        if b._k >= 2:
            on = b._k - 1
        if sn != 0 or on != 0:
            if on == 1 and sn == 0:
                return _ail_dec_pos_nr(a, ctx)
            if sn == 1 and on == 0:
                return _ail_dec_pos_nr(b, ctx)
            return _ail_dec_nan2(a, b, ctx)
    c = _ail_dec_cmp(a, b)
    if c == 0:
        if a._k == 1 and b._k == 1:
            c = 0
            if a._s != b._s:
                if a._s == 1:
                    c = -1
                else:
                    c = 1
        else:
            c = _ail_dec_total_finite(a, b)
    if want_max:
        if c == -1:
            return _ail_dec_pos_nr(b, ctx)
        return _ail_dec_pos_nr(a, ctx)
    if c == -1:
        return _ail_dec_pos_nr(a, ctx)
    return _ail_dec_pos_nr(b, ctx)


def _ail_dec_pos_nr(d, ctx):
    # d._fix(ctx)
    if d._k == 1:
        return d
    if d._k >= 2:
        return _ail_dec_fix_nan(d, ctx)
    return _ail_dec_fix(d._s, d._c, d._e, ctx)


# ---------------------------------------------------------------------------------------------------------------
# + - * / // % divmod
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_add(a, b, ctx):
    if a._k != 0 or b._k != 0:
        r = _ail_dec_nan2(a, b, ctx)
        if r is not None:
            return r
        if a._k == 1:
            if a._s != b._s and b._k == 1:
                _ail_dec_invalid("InvalidOperation")
            return a
        if b._k == 1:
            return b
    exp = a._e
    if b._e < exp:
        exp = b._e
    negzero = 0
    if ctx.rounding == "ROUND_FLOOR" and a._s != b._s:
        negzero = 1
    if a._c == 0 and b._c == 0:
        sign = a._s
        if b._s < sign:
            sign = b._s
        if negzero == 1:
            sign = 1
        return _ail_dec_fix(sign, 0, exp, ctx)
    if a._c == 0:
        exp = max(exp, b._e - ctx.prec - 1)
        t = _ail_dec_rescale(b, exp, ctx.rounding)
        return _ail_dec_fix(t._s, t._c, t._e, ctx)
    if b._c == 0:
        exp = max(exp, a._e - ctx.prec - 1)
        t = _ail_dec_rescale(a, exp, ctx.rounding)
        return _ail_dec_fix(t._s, t._c, t._e, ctx)
    # _normalize: the operand with the larger exponent is scaled down to the other's exponent, the other
    # one is replaced by a tiny value when it lies far below the precision
    ac = a._c
    ae = a._e
    bc = b._c
    be = b._e
    prec = ctx.prec
    if ae < be:
        tl = _ail_dec_nd(bc)
        ol = _ail_dec_nd(ac)
        ne = be + min(-1, tl - prec - 2)
        if ol + ae - 1 < ne:
            ac = 1
            ae = ne
        bc = bc * _ail_dec_p10(be - ae)
        be = ae
    else:
        tl = _ail_dec_nd(ac)
        ol = _ail_dec_nd(bc)
        ne = ae + min(-1, tl - prec - 2)
        if ol + be - 1 < ne:
            bc = 1
            be = ne
        ac = ac * _ail_dec_p10(ae - be)
        ae = be
    x = ac
    if a._s == 1:
        x = -x
    y = bc
    if b._s == 1:
        y = -y
    t = x + y
    if t == 0:
        return _ail_dec_fix(negzero, 0, exp, ctx)
    if t < 0:
        return _ail_dec_fix(1, -t, ae, ctx)
    return _ail_dec_fix(0, t, ae, ctx)


def _ail_dec_sub(a, b, ctx):
    if a._k >= 2 or b._k >= 2:
        r = _ail_dec_nan2(a, b, ctx)
        if r is not None:
            return r
    return _ail_dec_add(a, _ail_dec_mk(1 - b._s, b._c, b._e, b._k), ctx)


def _ail_dec_mul(a, b, ctx):
    sign = a._s ^ b._s
    if a._k != 0 or b._k != 0:
        r = _ail_dec_nan2(a, b, ctx)
        if r is not None:
            return r
        if a._k == 1:
            if b._k == 0 and b._c == 0:
                _ail_dec_invalid("InvalidOperation")
            return _ail_dec_inf(sign)
        if b._k == 1:
            if a._c == 0:
                _ail_dec_invalid("InvalidOperation")
            return _ail_dec_inf(sign)
    return _ail_dec_fix(sign, a._c * b._c, a._e + b._e, ctx)


def _ail_dec_div(a, b, ctx):
    sign = a._s ^ b._s
    if a._k != 0 or b._k != 0:
        r = _ail_dec_nan2(a, b, ctx)
        if r is not None:
            return r
        if a._k == 1 and b._k == 1:
            _ail_dec_invalid("InvalidOperation")
        if a._k == 1:
            return _ail_dec_inf(sign)
        if b._k == 1:
            return _ail_dec_mk(sign, 0, ctx.Emin - ctx.prec + 1, 0)
    if b._c == 0:
        if a._c == 0:
            _ail_dec_invalid("DivisionUndefined")
        raise DivisionByZero("[<class 'decimal.DivisionByZero'>]")
    if a._c == 0:
        return _ail_dec_fix(sign, 0, a._e - b._e, ctx)
    shift = _ail_dec_nd(b._c) - _ail_dec_nd(a._c) + ctx.prec + 1
    exp = a._e - b._e - shift
    if shift >= 0:
        coeff = (a._c * _ail_dec_p10(shift)) // b._c
        rem = (a._c * _ail_dec_p10(shift)) % b._c
    else:
        coeff = a._c // (b._c * _ail_dec_p10(-shift))
        rem = a._c % (b._c * _ail_dec_p10(-shift))
    if rem != 0:
        if coeff % 5 == 0:
            coeff = coeff + 1
    else:
        ideal = a._e - b._e
        while exp < ideal and coeff % 10 == 0:
            coeff = coeff // 10
            exp = exp + 1
    return _ail_dec_fix(sign, coeff, exp, ctx)


def _ail_dec_divide(a, b, ctx) -> list:
    # [self // other, self % other] to the precision of the context; a is finite, b nonzero, no NaN
    sign = a._s ^ b._s
    if b._k == 1:
        ideal = a._e
    else:
        ideal = min(a._e, b._e)
    expdiff = _ail_dec_adjusted(a) - _ail_dec_adjusted(b)
    if (a._k == 0 and a._c == 0) or b._k == 1 or expdiff <= -2:
        return [_ail_dec_mk(sign, 0, 0, 0), _ail_dec_rescale(a, ideal, ctx.rounding)]
    if expdiff <= ctx.prec:
        x = a._c
        y = b._c
        if a._e >= b._e:
            x = x * _ail_dec_p10(a._e - b._e)
        else:
            y = y * _ail_dec_p10(b._e - a._e)
        q = x // y
        r = x % y
        if q < _ail_dec_p10(ctx.prec):
            return [_ail_dec_mk(sign, q, 0, 0), _ail_dec_mk(a._s, r, ideal, 0)]
    _ail_dec_invalid("DivisionImpossible")
    return [a, a]


def _ail_dec_qcheck(q, ctx):
    # the integer quotient must fit under Emax
    if q._k == 0 and q._c != 0 and _ail_dec_adjusted(q) > ctx.Emax:
        raise Overflow("[<class 'decimal.Overflow'>]")
    return q


def _ail_dec_floordiv(a, b, ctx):
    r = _ail_dec_nan2(a, b, ctx)
    if r is not None:
        return r
    if a._k == 1:
        if b._k == 1:
            _ail_dec_invalid("InvalidOperation")
        return _ail_dec_inf(a._s ^ b._s)
    if b._k == 0 and b._c == 0:
        if a._c != 0:
            raise DivisionByZero("[<class 'decimal.DivisionByZero'>]")
        _ail_dec_invalid("DivisionUndefined")
    return _ail_dec_qcheck(_ail_dec_divide(a, b, ctx)[0], ctx)


def _ail_dec_mod(a, b, ctx):
    r = _ail_dec_nan2(a, b, ctx)
    if r is not None:
        return r
    if a._k == 1:
        _ail_dec_invalid("InvalidOperation")
    if b._k == 0 and b._c == 0:
        if a._c != 0:
            _ail_dec_invalid("InvalidOperation")
        _ail_dec_invalid("DivisionUndefined")
    t = _ail_dec_divide(a, b, ctx)[1]
    return _ail_dec_fix(t._s, t._c, t._e, ctx)


def _ail_dec_divmod(a, b, ctx):
    r = _ail_dec_nan2(a, b, ctx)
    if r is not None:
        return (r, r)
    sign = a._s ^ b._s
    if a._k == 1:
        _ail_dec_invalid("InvalidOperation")
    if b._k == 0 and b._c == 0:
        if a._c != 0:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>, <class 'decimal.DivisionByZero'>]")
        _ail_dec_invalid("DivisionUndefined")
    qr = _ail_dec_divide(a, b, ctx)
    t = qr[1]
    q = qr[0]
    return (_ail_dec_qcheck(q, ctx), _ail_dec_fix(t._s, t._c, t._e, ctx))


# ---------------------------------------------------------------------------------------------------------------
# power (integer exponents; a fractional exponent is the one thing that needs ln and exp)
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_isint(d) -> bool:
    if d._k != 0:
        return False
    if d._e >= 0:
        return True
    if d._c == 0:
        return True
    return d._c % _ail_dec_p10(-d._e) == 0


def _ail_dec_pow(a, b, ctx):
    r = _ail_dec_nan2(a, b, ctx)
    if r is not None:
        return r
    if b._k == 0 and b._c == 0:
        if a._k == 0 and a._c == 0:
            _ail_dec_invalid("InvalidOperation")
        return Decimal(1)
    result_sign = 0
    x = a
    if a._s == 1:
        if _ail_dec_isint(b):
            bi = _ail_dec_toint(b)
            if bi % 2 != 0:
                result_sign = 1
        else:
            if not (a._k == 0 and a._c == 0):
                _ail_dec_invalid("InvalidOperation")
        x = _ail_dec_mk(0, a._c, a._e, a._k)
    if x._k == 0 and x._c == 0:
        if b._s == 0:
            return _ail_dec_mk(result_sign, 0, 0, 0)
        return _ail_dec_inf(result_sign)
    if x._k == 1:
        if b._s == 0:
            return _ail_dec_inf(result_sign)
        return _ail_dec_mk(result_sign, 0, 0, 0)
    if _ail_dec_cmp(x, Decimal(1)) == 0:
        # 1 ** y: the exponent depends on the exponent of x and on whether y is a positive integer
        if _ail_dec_isint(b):
            if b._s == 1:
                mult = 0
            elif _ail_dec_cmp(b, Decimal(ctx.prec)) > 0:
                mult = ctx.prec
            else:
                mult = _ail_dec_toint(b)
            exp = x._e * mult
            if exp < 1 - ctx.prec:
                exp = 1 - ctx.prec
        else:
            exp = 1 - ctx.prec
        if exp < 0:
            return _ail_dec_mk(result_sign, _ail_dec_p10(-exp), exp, 0)
        return _ail_dec_mk(result_sign, 1, exp, 0)
    if b._k == 1:
        xa = _ail_dec_adjusted(x)
        if (b._s == 0) == (xa < 0):
            return _ail_dec_mk(result_sign, 0, 0, 0)
        return _ail_dec_inf(result_sign)
    if not _ail_dec_isint(b):
        raise RuntimeError("decimal ** with a non-integer exponent is not built")
    n = _ail_dec_toint(b)
    return _ail_dec_pow_int(x, b, n, result_sign, ctx)


def _ail_dec_pow_int(x, b, n: int, sign: int, ctx):
    # x finite, nonzero, positive; b an integer-valued Decimal, n its value. The algorithm of libmpdec (what
    # CPython runs): square-and-multiply with every product rounded to a work precision (half even), the
    # exponent being negative first taking the reciprocal of x, then one final rounding by the context.
    an = n
    if an < 0:
        an = -an
    if an.bit_length() > 64:
        raise RuntimeError("decimal ** with this exponent is not built")
    w = ctx.copy()
    w.prec = ctx.prec + _ail_dec_nd(b._c) + b._e + 2
    w.rounding = "ROUND_HALF_EVEN"
    w.clamp = 0
    base = x
    if n < 0:
        w.prec = w.prec + 1
        base = _ail_dec_div(_ail_dec_mk(0, 1, 0, 0), x, w)
    r = base
    bits = an.bit_length()
    i = bits - 2
    while i >= 0:
        r = _ail_dec_mul(r, r, w)
        if (an >> i) & 1 == 1:
            r = _ail_dec_mul(r, base, w)
        i = i - 1
    return _ail_dec_fix(sign, r._c, r._e, ctx)


# ---------------------------------------------------------------------------------------------------------------
# format
# ---------------------------------------------------------------------------------------------------------------
def _ail_dec_format(d, spec: str) -> str:
    n = len(spec)
    i = 0
    fill = " "
    align = ""
    if n >= 2 and (spec[1] == "<" or spec[1] == ">" or spec[1] == "=" or spec[1] == "^"):
        fill = spec[0]
        align = spec[1]
        i = 2
    elif n >= 1 and (spec[0] == "<" or spec[0] == ">" or spec[0] == "=" or spec[0] == "^"):
        align = spec[0]
        i = 1
    fsign = "-"
    if i < n and (spec[i] == "-" or spec[i] == "+" or spec[i] == " "):
        fsign = spec[i]
        i = i + 1
    noneg0 = False
    if i < n and spec[i] == "z":
        noneg0 = True
        i = i + 1
    alt = False
    if i < n and spec[i] == "#":
        alt = True
        i = i + 1
    zeropad = False
    if i < n and spec[i] == "0":
        zeropad = True
        i = i + 1
    width = 0
    j = i
    while j < n and "0" <= spec[j] <= "9":
        j = j + 1
    if j > i:
        if spec[i] == "0":
            raise ValueError("invalid format string")
        width = int(spec[i:j])
        i = j
    sep = ""
    if i < n and spec[i] == ",":
        sep = ","
        i = i + 1
    prec = -1
    if i < n and spec[i] == ".":
        j = i + 1
        while j < n and "0" <= spec[j] <= "9":
            j = j + 1
        if j == i + 1:
            raise ValueError("invalid format string")
        if spec[i + 1] == "0" and j > i + 2:
            raise ValueError("invalid format string")
        prec = int(spec[i + 1:j])
        i = j
    typ = ""
    if i < n and (spec[i] == "e" or spec[i] == "E" or spec[i] == "f" or spec[i] == "F" or spec[i] == "g"
                  or spec[i] == "G" or spec[i] == "n" or spec[i] == "%"):
        typ = spec[i]
        i = i + 1
    if i != n:
        raise ValueError("invalid format string")
    if zeropad and (align != "" or fill != " "):
        raise ValueError("invalid format string")
    if align == "":
        align = ">"
    if prec == 0 and (typ == "" or typ == "g" or typ == "G" or typ == "n"):
        prec = 1
    if typ == "n":
        typ = "g"
    ctx = _ail_dec_ctx
    if d._k != 0:
        sg = _ail_dec_fsign(d._s, fsign)
        body = _ail_dec_str(_ail_dec_mk(0, d._c, d._e, d._k), False)
        if typ == "%":
            body = body + "%"
        return _ail_dec_align(sg, body, width, fill, align)
    if typ == "":
        if ctx.capitals == 1:
            typ = "G"
        else:
            typ = "g"
    s = d._s
    c = d._c
    e = d._e
    if typ == "%":
        e = e + 2
    t = _ail_dec_mk(s, c, e, 0)
    if prec >= 0:
        if typ == "e" or typ == "E":
            t = _ail_dec_round_sig(t, prec + 1, ctx.rounding)
        elif typ == "f" or typ == "F" or typ == "%":
            t = _ail_dec_rescale(t, -prec, ctx.rounding)
        elif (typ == "g" or typ == "G") and _ail_dec_nd(t._c) > prec:
            t = _ail_dec_round_sig(t, prec, ctx.rounding)
    if t._c == 0 and t._e > 0 and (typ == "f" or typ == "F" or typ == "%"):
        t = _ail_dec_rescale(t, 0, ctx.rounding)
    asign = t._s
    if t._c == 0 and noneg0 and t._s == 1:
        asign = 0
    digs = _ail_dec_digs(t._c)
    nd = len(digs)
    leftdigits = t._e + nd
    if typ == "e" or typ == "E":
        if t._c == 0 and prec >= 0:
            dotplace = 1 - prec
        else:
            dotplace = 1
    elif typ == "f" or typ == "F" or typ == "%":
        dotplace = leftdigits
    else:
        if t._e <= 0 and leftdigits > -6:
            dotplace = leftdigits
        else:
            dotplace = 1
    if dotplace < 0:
        intpart = "0"
        fracpart = "0" * (-dotplace) + digs
    elif dotplace > nd:
        intpart = digs + "0" * (dotplace - nd)
        fracpart = ""
    else:
        intpart = digs[:dotplace]
        if intpart == "":
            intpart = "0"
        fracpart = digs[dotplace:]
    exp = leftdigits - dotplace
    sg = _ail_dec_fsign(asign, fsign)
    if fracpart != "" or alt:
        fracpart = "." + fracpart
    if exp != 0 or typ == "e" or typ == "E":
        ech = "e"
        if typ == "E" or typ == "G":
            ech = "E"
        es = str(exp)
        if exp >= 0:
            es = "+" + es
        fracpart = fracpart + ech + es
    if typ == "%":
        fracpart = fracpart + "%"
    minw = 0
    if zeropad:
        minw = width - len(fracpart) - len(sg)
    if sep != "":
        intpart = _ail_dec_group(intpart, minw)
    elif minw > len(intpart):
        intpart = "0" * (minw - len(intpart)) + intpart
    return _ail_dec_align(sg, intpart + fracpart, width, fill, align)


def _ail_dec_round_sig(t, places: int, mode: str):
    # t rounded to `places` significant digits (a finite value; zero is returned as it is)
    if t._c == 0:
        return t
    r = _ail_dec_rescale(t, _ail_dec_adjusted(t) + 1 - places, mode)
    if _ail_dec_adjusted(r) != _ail_dec_adjusted(t):
        r = _ail_dec_rescale(r, _ail_dec_adjusted(r) + 1 - places, mode)
    return r


def _ail_dec_fsign(neg: int, fsign: str) -> str:
    if neg == 1:
        return "-"
    if fsign == "+" or fsign == " ":
        return fsign
    return ""


def _ail_dec_align(sg: str, body: str, width: int, fill: str, align: str) -> str:
    pad = fill * (width - len(sg) - len(body))
    if align == "<":
        return sg + body + pad
    if align == ">":
        return pad + sg + body
    if align == "=":
        return sg + pad + body
    half = len(pad) // 2
    return pad[:half] + sg + body + pad[half:]


def _ail_dec_group(digits: str, min_width: int) -> str:
    # thousands separators (groups of 3), zero padded on the left to min_width without a leading comma
    groups = []
    while True:
        l = max(len(digits), min_width, 1)
        if l > 3:
            l = 3
        groups.append("0" * (l - len(digits)) + digits[-l:])
        digits = digits[:-l]
        min_width = min_width - l
        if digits == "" and min_width <= 0:
            break
        min_width = min_width - 1
    groups.reverse()
    return ",".join(groups)
