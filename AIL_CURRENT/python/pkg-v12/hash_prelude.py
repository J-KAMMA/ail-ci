# -*- coding: utf-8 -*-
"""hash_prelude.py -- the Python source hashlower.py injects for hashlib, hmac, secrets, base64 and the integer/bytes
conversions (docs/design/CRYPTO.md).

Ordinary Python in the subset both compile paths build (no default arguments: hashlower.py fills them in, no tuples,
no properties). hashlower.py parses it, keeps the definitions a program reaches (a definition names the others it
needs by using them) and puts them in front of the program. The C primitives (`_ail_hs_*`, ailhash_core.h) are
listed in hashlower.HASHP; on the general path hashlower wraps every bytes argument of a primitive in `_ail_bs(..)`
and its bytes result in `_ail_mkb(..)`, because a bytes value there is an object holding a str.

Where CPython 3.12 has the behaviour, the comment says which function it is taken from:
  hashlib.py / _hashopenssl.c   new, the constructors, unsupported hash type, pbkdf2_hmac checks
  _blake2/blake2b_impl.c        digest_size, key, salt and person limits
  hmac.py / _hashopenssl.c      HMAC, digest, compare_digest
  secrets.py / random.py        token_*, randbelow (SystemRandom._randbelow_with_getrandbits), choice
  base64.py / binascii.c        b64encode, b64decode (a2b_base64), urlsafe_*
  Objects/longobject.c          int.to_bytes, int.from_bytes
"""


# ------------------------------------------------------------------------------------------ hashlib

class _AilHash:
    def __init__(self, st: bytes, name: str, size: int, block: int):
        self.st = st
        self.name = name
        self.digest_size = size
        self.block_size = block

    def update(self, data: bytes) -> None:
        self.st = _ail_hs_update(self.st, data)

    def digest(self) -> bytes:
        return _ail_hs_digest(self.st)

    def hexdigest(self) -> str:
        return _ail_hs_digest(self.st).hex()

    def copy(self) -> "_AilHash":
        return _AilHash(self.st, self.name, self.digest_size, self.block_size)


def _ail_hl_name(algo: int) -> str:
    names = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_224", "sha3_256", "sha3_384", "sha3_512",
             "blake2b", "blake2s"]
    return names[algo]


def _ail_hl_new(algo: int, data: bytes, size: int, key: bytes, salt: bytes, person: bytes) -> _AilHash:
    st = _ail_hs_new(algo, size, key, salt, person)
    if len(data) > 0:
        st = _ail_hs_update(st, data)
    return _AilHash(st, _ail_hl_name(algo), _ail_hs_info(st, 0), _ail_hs_info(st, 1))


# blake2b(data, digest_size=, key=, salt=, person=): size -1 is "not given"
def _ail_hl_blake(algo: int, data: bytes, size: int, key: bytes, salt: bytes, person: bytes) -> _AilHash:
    top = 64
    smax = 16
    if algo == 11:
        top = 32
        smax = 8
    sz = size
    if size == -1:
        sz = 0
    elif size < 1 or size > top:
        raise ValueError("digest_size must be between 1 and " + str(top) + " bytes")
    if len(key) > top:
        raise ValueError("maximum key length is " + str(top) + " bytes")
    if len(salt) > smax:
        raise ValueError("maximum salt length is " + str(smax) + " bytes")
    if len(person) > smax:
        raise ValueError("maximum person length is " + str(smax) + " bytes")
    return _ail_hl_new(algo, data, sz, key, salt, person)


def _ail_hl_algo(name: str) -> int:
    a = _ail_hs_algo(name)
    if a < 0:
        raise ValueError("unsupported hash type " + name)
    return a


def _ail_hl_by_name(name: str, data: bytes) -> _AilHash:
    return _ail_hl_new(_ail_hl_algo(name), data, 0, b"", b"", b"")


def _ail_hl_pbkdf2(name: str, pw: bytes, salt: bytes, iters: int, dklen: int) -> bytes:
    a = _ail_hs_algo(name)
    if a < 0:
        raise ValueError("[digital envelope routines] unsupported")
    if iters < 1:
        raise ValueError("iteration value must be greater than 0.")
    dk = dklen
    if dklen == -1:
        dk = _ail_hs_info(_ail_hs_new(a, 0, b"", b"", b""), 0)
    if dk < 1:
        raise ValueError("key length must be greater than 0.")
    return _ail_hs_pbkdf2(a, pw, salt, iters, dk)


# ------------------------------------------------------------------------------------------ hmac

class _AilHmac:
    def __init__(self, st: bytes, name: str, size: int, block: int):
        self.st = st
        self.name = name
        self.digest_size = size
        self.block_size = block

    def update(self, msg: bytes) -> None:
        self.st = _ail_hs_update(self.st, msg)

    def digest(self) -> bytes:
        return _ail_hs_digest(self.st)

    def hexdigest(self) -> str:
        return _ail_hs_digest(self.st).hex()

    def copy(self) -> "_AilHmac":
        return _AilHmac(self.st, self.name, self.digest_size, self.block_size)


def _ail_hl_hmac(algo: int, key: bytes, msg: bytes) -> _AilHmac:
    st = _ail_hs_hmac(algo, key)
    if len(msg) > 0:
        st = _ail_hs_update(st, msg)
    return _AilHmac(st, "hmac-" + _ail_hl_name(algo), _ail_hs_info(st, 0), _ail_hs_info(st, 1))


def _ail_hl_hmac_missing() -> _AilHmac:
    raise TypeError("Missing required argument 'digestmod'.")


def _ail_hl_hmac_digest(algo: int, key: bytes, msg: bytes) -> bytes:
    return _ail_hs_digest(_ail_hs_update(_ail_hs_hmac(algo, key), msg))


def _ail_hl_cmp(a: bytes, b: bytes) -> bool:
    return _ail_hs_cmp(a, b) == 1


def _ail_hl_ascii(text: str) -> bool:
    for c in text:
        if ord(c) > 127:
            return False
    return True


def _ail_hl_cmp_str(a: str, b: str) -> bool:
    if not _ail_hl_ascii(a) or not _ail_hl_ascii(b):
        raise TypeError("comparing strings with non-ASCII characters is not supported")
    return _ail_hs_cmp(a.encode(), b.encode()) == 1


# the general path: types are dynamic, so one function takes a str or a bytes-like value
def _ail_hl_cmp_dyn(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return _ail_hl_cmp_str(a, b)
    return _ail_hl_cmp(a, b)


# ------------------------------------------------------------------------------------------ secrets

def _ail_hl_token_bytes(n: int) -> bytes:
    if n < 0:
        raise ValueError("negative argument not allowed")
    return _ail_hs_rand(n)


def _ail_hl_token_hex(n: int) -> str:
    return _ail_hl_token_bytes(n).hex()


def _ail_hl_token_urlsafe(n: int) -> str:
    e = _ail_hs_b64e(_ail_hl_token_bytes(n), 1)
    k = len(e)
    while k > 0 and e[k - 1] == 61:
        k -= 1
    return e[0:k].decode()


def _ail_hl_randbits(k: int) -> int:
    if k < 0:
        raise ValueError("number of bits must be non-negative")
    if k > 63:
        raise OverflowError("randbits wider than 63 bits needs integers wider than 64 bits")
    return _ail_hs_bits(k)


def _ail_hl_randbelow(n: int) -> int:
    if n <= 0:
        raise ValueError("Upper bound must be positive.")
    k = 0
    t = n
    while t > 0:
        k += 1
        t = t >> 1
    r = _ail_hs_bits(k)
    while r >= n:
        r = _ail_hs_bits(k)
    return r


def _ail_hl_index(n: int) -> int:
    if n == 0:
        raise IndexError("Cannot choose from an empty sequence")
    return _ail_hl_randbelow(n)


# ------------------------------------------------------------------------------------------ base64

class Error(ValueError):
    pass


def _ail_hl_b64msg(code: int, n: int) -> str:
    if code == 1:
        return "Incorrect padding"
    if code == 2:
        return "Invalid base64-encoded string: number of data characters (" + str(n) + ") cannot be 1 more than a multiple of 4"
    if code == 3:
        return "Only base64 data is allowed"
    if code == 4:
        return "Excess data after padding"
    if code == 5:
        return "Leading padding not allowed"
    return "Discontinuous padding not allowed"


def _ail_hl_b64e(data: bytes, urlsafe: int) -> bytes:
    return _ail_hs_b64e(data, urlsafe)


def _ail_hl_b64d(data: bytes, mode: int) -> bytes:
    r = _ail_hs_b64d(data, mode)
    e = _ail_hs_b64err()
    if e != 0:
        raise Error(_ail_hl_b64msg(e, _ail_hs_b64n()))
    return r


def _ail_hl_b64d_str(text: str, mode: int) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_b64d(text.encode(), mode)


def _ail_hl_b64d_dyn(data, mode):
    if isinstance(data, str):
        return _ail_hl_b64d_str(data, mode)
    return _ail_hl_b64d(data, mode)


def _ail_hl_flag(flag: bool) -> int:
    if flag:
        return 1
    return 0


def _ail_hl_b64_mode(urlsafe: int, validate: bool) -> int:
    if validate:
        return urlsafe + 2
    return urlsafe


def _ail_hl_typefail(data, kind: int) -> None:
    name = type(data).__name__
    if kind == 0:
        raise TypeError("a bytes-like object is required, not '" + name + "'")
    if kind == 1:
        raise TypeError("memoryview: a bytes-like object is required, not '" + name + "'")
    if kind == 3:
        raise TypeError("argument should be a bytes-like object or ASCII string, not '" + name + "'")
    raise TypeError("expected bytes-like object, not " + name)


def _ail_hl_need_bytes(data, kind: int):
    if isinstance(data, bytes) or isinstance(data, bytearray):
        return data
    _ail_hl_typefail(data, kind)
    return data


def _ail_hl_bs_in(data: bytes) -> bytes:
    if isinstance(data, bytearray):
        return bytes(data)
    return data


def _ail_hl_alt_bytes(data: bytes, kind: int) -> bytes:
    assert len(data) == 2, repr(data)
    return _ail_hl_need_bytes(data, kind)


def _ail_hl_alt_str(text: str) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_alt_bytes(text.encode(), 3)


def _ail_hl_alt_dyn(data):
    if isinstance(data, str):
        return _ail_hl_alt_str(data)
    _ail_hl_need_bytes(data, 3)
    return _ail_hl_alt_bytes(data, 3)


def _ail_hl_alt_enc_dyn(data):
    if isinstance(data, str):
        if len(data) != 2:
            raise AssertionError(repr(data))
        raise TypeError("a bytes-like object is required, not 'str'")
    return _ail_hl_alt_bytes(data, 0)


def _ail_hl_b64e_alt(data: bytes, altchars) -> bytes:
    e = _ail_hl_b64e(data, 0)
    if altchars is None:
        return e
    altchars = _ail_hl_alt_bytes(altchars, 0)
    out = bytearray()
    for c in e:
        if c == 43:
            out.append(altchars[0])
        elif c == 47:
            out.append(altchars[1])
        else:
            out.append(c)
    return bytes(out)


def _ail_hl_b64d_alt(data, altchars, mode: int) -> bytes:
    data = _ail_hl_need_bytes(data, 3)
    if altchars is None:
        return _ail_hl_b64d(data, mode)
    altchars = _ail_hl_alt_dyn(altchars)
    out = bytearray()
    for c in data:
        if c == altchars[1]:
            out.append(47)
        elif c == altchars[0]:
            out.append(43)
        else:
            out.append(c)
    return _ail_hl_b64d(bytes(out), mode)


def _ail_hl_b64d_alt_str(text: str, altchars, mode: int) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_b64d_alt(text.encode(), altchars, mode)


def _ail_hl_b64d_alt_dyn(data, altchars, mode):
    if isinstance(data, str):
        if not _ail_hl_ascii(data):
            raise ValueError("string argument should contain only ASCII characters")
        data = data.encode()
    return _ail_hl_b64d_alt(data, altchars, mode)


def _ail_hl_b16val(c: int, casefold: int) -> int:
    if c >= 48 and c <= 57:
        return c - 48
    if c >= 65 and c <= 70:
        return c - 55
    if casefold != 0 and c >= 97 and c <= 102:
        return c - 87
    return -1


def _ail_hl_b16e(data: bytes) -> bytes:
    data = _ail_hl_need_bytes(data, 0)
    out = bytearray()
    for c in data:
        hi = c >> 4
        lo = c & 15
        if hi < 10:
            out.append(48 + hi)
        else:
            out.append(65 + hi - 10)
        if lo < 10:
            out.append(48 + lo)
        else:
            out.append(65 + lo - 10)
    return bytes(out)


def _ail_hl_b16d(data: bytes, casefold: int) -> bytes:
    i = 0
    while i < len(data):
        if _ail_hl_b16val(data[i], casefold) < 0:
            raise Error("Non-base16 digit found")
        i += 1
    if len(data) % 2 != 0:
        raise Error("Odd-length string")
    out = bytearray()
    i = 0
    while i < len(data):
        out.append(_ail_hl_b16val(data[i], casefold) * 16 + _ail_hl_b16val(data[i + 1], casefold))
        i += 2
    return bytes(out)


def _ail_hl_b16d_str(text: str, casefold: int) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_b16d(text.encode(), casefold)


def _ail_hl_b16d_dyn(data, casefold):
    if isinstance(data, str):
        return _ail_hl_b16d_str(data, casefold)
    _ail_hl_need_bytes(data, 3)
    return _ail_hl_b16d(data, casefold)


def _ail_hl_b32val(c: int) -> int:
    if c >= 65 and c <= 90:
        return c - 65
    if c >= 50 and c <= 55:
        return c - 24
    return -1


def _ail_hl_b32e(data: bytes) -> bytes:
    data = _ail_hl_need_bytes(data, 1)
    alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    out = bytearray()
    n = len(data)
    rem = 0
    i = 0
    while i < n:
        rem = n - i
        b0 = data[i]
        b1 = data[i + 1] if rem > 1 else 0
        b2 = data[i + 2] if rem > 2 else 0
        b3 = data[i + 3] if rem > 3 else 0
        b4 = data[i + 4] if rem > 4 else 0
        out.append(alphabet[b0 >> 3])
        out.append(alphabet[((b0 & 7) << 2) | (b1 >> 6)])
        out.append(alphabet[(b1 >> 1) & 31])
        out.append(alphabet[((b1 & 1) << 4) | (b2 >> 4)])
        out.append(alphabet[((b2 & 15) << 1) | (b3 >> 7)])
        out.append(alphabet[(b3 >> 2) & 31])
        out.append(alphabet[((b3 & 3) << 3) | (b4 >> 5)])
        out.append(alphabet[b4 & 31])
        i += 5
    pad = 0
    if rem == 1:
        pad = 6
    elif rem == 2:
        pad = 4
    elif rem == 3:
        pad = 3
    elif rem == 4:
        pad = 1
    j = 0
    while j < pad:
        out[len(out) - 1 - j] = 61
        j += 1
    return bytes(out)


def _ail_hl_b32d(data: bytes, casefold: int) -> bytes:
    data = _ail_hl_bs_in(data)
    s = data
    if casefold != 0:
        up = bytearray()
        for c in s:
            if c >= 97 and c <= 122:
                up.append(c - 32)
            else:
                up.append(c)
        s = bytes(up)
    if len(s) % 8 != 0:
        raise Error("Incorrect padding")
    total = len(s)
    k = total
    while k > 0 and s[k - 1] == 61:
        k -= 1
    padchars = total - k
    decoded = bytearray()
    acc = 0
    i = 0
    while i < k:
        acc = 0
        j = 0
        while j < 8 and i + j < k:
            v = _ail_hl_b32val(s[i + j])
            if v < 0:
                raise Error("Non-base32 digit found")
            acc = (acc << 5) + v
            j += 1
        while j < 8:
            acc = acc << 5
            j += 1
        decoded.append((acc >> 32) & 255)
        decoded.append((acc >> 24) & 255)
        decoded.append((acc >> 16) & 255)
        decoded.append((acc >> 8) & 255)
        decoded.append(acc & 255)
        i += 8
    if padchars != 0 and padchars != 1 and padchars != 3 and padchars != 4 and padchars != 6:
        raise Error("Incorrect padding")
    if padchars > 0 and len(decoded) > 0:
        leftover = (43 - 5 * padchars) // 8
        del decoded[len(decoded) - (5 - leftover):]
    return bytes(decoded)


def _ail_hl_b32d_str(text: str, casefold: int) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_b32d(text.encode(), casefold)


def _ail_hl_b32d_dyn(data, casefold):
    if isinstance(data, str):
        return _ail_hl_b32d_str(data, casefold)
    _ail_hl_need_bytes(data, 3)
    return _ail_hl_b32d(data, casefold)


def _ail_hl_encodebytes(data: bytes) -> bytes:
    data = _ail_hl_need_bytes(data, 2)
    out = bytearray()
    i = 0
    while i < len(data):
        piece = _ail_hl_b64e(data[i:i + 57], 0)
        for c in piece:
            out.append(c)
        out.append(10)
        i += 57
    return bytes(out)


def _ail_hl_decodebytes(data: bytes) -> bytes:
    data = _ail_hl_need_bytes(data, 2)
    return _ail_hl_b64d(data, 0)


def _ail_hl_decodebytes_str(text: str) -> bytes:
    _ail_hl_typefail(text, 2)
    return _ail_hl_b64d(text.encode(), 0)


def _ail_hl_decodebytes_dyn(data):
    data = _ail_hl_need_bytes(data, 2)
    return _ail_hl_b64d(data, 0)


# ------------------------------------------------------------------------------------------ int <-> bytes

def _ail_hl_from_bytes(data: bytes, order: str, signed: bool) -> int:
    if order != "big" and order != "little":
        raise ValueError("byteorder must be either 'little' or 'big'")
    n = len(data)
    v = 0
    i = 0
    while i < n:
        if order == "big":
            b = data[i]
        else:
            b = data[n - 1 - i]
        if i == 0 and signed and b >= 128:
            b = b - 256
        v = v * 256 + b
        i += 1
    return v


def _ail_hl_to_bytes(x: int, length: int, order: str, signed: bool) -> bytes:
    if order != "big" and order != "little":
        raise ValueError("byteorder must be either 'little' or 'big'")
    if length < 0:
        raise ValueError("length argument must be non-negative")
    if x < 0 and not signed:
        raise OverflowError("can't convert negative int to unsigned")
    out = bytearray(length)
    v = x
    i = 0
    while i < length:
        if order == "big":
            out[length - 1 - i] = v & 255
        else:
            out[i] = v & 255
        v = v >> 8
        i += 1
    if signed:
        if length == 0:
            ok = x == 0 or x == -1          # CPython: (-1).to_bytes(0, signed=True) is b""
        else:
            if order == "big":
                top = out[0]
            else:
                top = out[length - 1]
            ok = (v == 0 and top < 128) or (v == -1 and top >= 128)
        if not ok:
            raise OverflowError("int too big to convert")
    elif v != 0:
        raise OverflowError("int too big to convert")
    return bytes(out)
