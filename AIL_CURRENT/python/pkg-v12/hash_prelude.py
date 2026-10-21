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
        raise ValueError(_ail_hl_b64msg(e, _ail_hs_b64n()))
    return r


def _ail_hl_b64d_str(text: str, mode: int) -> bytes:
    if not _ail_hl_ascii(text):
        raise ValueError("string argument should contain only ASCII characters")
    return _ail_hl_b64d(text.encode(), mode)


def _ail_hl_b64d_dyn(data, mode):
    if isinstance(data, str):
        return _ail_hl_b64d_str(data, mode)
    return _ail_hl_b64d(data, mode)


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
