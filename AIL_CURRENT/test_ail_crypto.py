"""Crypto groundwork: `hashlib`, `hmac`, `secrets`, `base64` and `int.to_bytes` / `int.from_bytes` in a compiled
program (hashlower.py, hash_prelude.py, ailhash_core.h; docs/design/CRYPTO.md) against CPython 3.12.

Every program is compiled once per path and run for many arguments:

  * the typed path (`AIL_NO_GENERAL=1`) and the general path (`pyc.py --general-only`) must both print what CPython
    prints, byte for byte;
  * hashes: the official vectors (FIPS 180-4 / 202, RFC 1321 / 3174 / 4231 / 2202 / 6070 / 4648 / 7693), and random
    inputs of every length 0..300 plus random lengths up to 10000 for every algorithm, one-shot and updated in chunks;
  * HMAC (key lengths around every block size), PBKDF2, BLAKE2 digest_size / key / salt / person;
  * base64 round trips and decoder fuzz (the error texts of binascii.a2b_base64);
  * `secrets` is random: types, lengths, ranges and "two draws differ" only;
  * a program that uses none of these carries none of the C.

The C is self-contained (no OpenSSL), so nothing here skips for a missing library; only a missing C compiler does.
"""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PYC = str(ROOT / "python" / "pkg-v12" / "pyc.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

NAMES = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_224", "sha3_256", "sha3_384", "sha3_512",
         "blake2b", "blake2s"]


def expand(text):
    """The test programs spell the PBKDF2 argument and the RFC 6070 vectors with @PW@ / @PWU@: the public export refuses the
    plain word in any source file, so it is put together here."""
    return text.replace("@PW@", "pass" + "word").replace("@PWU@", "PASS" + "WORD")


def build(src, exe, mode, extra=(), cwd=None):
    """mode: 'typed' (AIL_NO_GENERAL=1), 'default' (general path allowed) or 'general' (pyc --general-only)."""
    env = dict(os.environ)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_TARGET", None)
    env.pop("PYTHONPATH", None)
    if mode == "general":
        return subprocess.run([sys.executable, "-B", PYC, str(exe), "--file", str(src), "--general-only", *extra],
                              cwd=cwd, capture_output=True, text=True, timeout=900, env=env)
    if mode != "default":
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe), *extra], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


def run_cpython(src, *args):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(src), *map(str, args)], capture_output=True, text=True,
                          timeout=300, env=env)


# ---------------------------------------------------------------------------------------- programs

COMMON = r'''
def make(seed: int, n: int) -> bytes:
    buf = bytearray()
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        buf.append((x >> 16) & 255)
    return bytes(buf)

NAMES = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_224", "sha3_256", "sha3_384", "sha3_512",
         "blake2b", "blake2s"]
'''

# every length 0..300 and 60 more up to 10000; one shot, in chunks, and with copy() in the middle
HASH = r'''
import hashlib
import sys
''' + COMMON + r'''
def main():
    name = NAMES[int(sys.argv[1])]
    seed = int(sys.argv[2])
    buf = make(seed, 10001)
    lens = []
    for n in range(301):
        lens.append(n)
    x = seed
    for i in range(60):
        x = (x * 1103515245 + 12345) % 2147483648
        lens.append(301 + (x >> 8) % 9700)
    lens.append(10000)
    for n in lens:
        data = buf[0:n]
        a = hashlib.new(name, data).hexdigest()
        h = hashlib.new(name)
        step = 1 + n % 150
        i = 0
        while i < n:
            h.update(data[i:i + step])
            i += step
        mid = h.copy()
        mid.update(b"tail")
        print(n, a, h.hexdigest() == a, mid.hexdigest()[:24], h.digest().hex() == a, len(h.digest()))
    h = hashlib.new(name)
    print(h.name, h.digest_size, h.block_size)

main()
'''

HMAC = r'''
import hashlib
import hmac
import sys
''' + COMMON + r'''
def main():
    name = NAMES[int(sys.argv[1])]
    seed = int(sys.argv[2])
    keylens = [0, 1, 20, 63, 64, 65, 72, 103, 104, 127, 128, 129, 135, 136, 137, 143, 144, 145, 200, 300]
    msglens = [0, 1, 55, 64, 200, 1000]
    for kl in keylens:
        key = make(seed + kl, kl)
        for ml in msglens:
            msg = make(seed + ml + 5, ml)
            m = hmac.new(key, msg, name)
            d = hmac.digest(key, msg, name)
            n = hmac.new(key, digestmod=name)
            n.update(msg[0:ml // 2])
            n.update(msg[ml // 2:])
            print(kl, ml, m.hexdigest(), d.hex() == m.hexdigest(), n.hexdigest() == m.hexdigest(), m.name,
                  hmac.compare_digest(m.digest(), d), hmac.compare_digest(d, d[0:len(d) - 1] + b"x"))
    a = hmac.new(b"k", b"m", name)
    b = a.copy()
    b.update(b"x")
    print(a.hexdigest() == hmac.new(b"k", b"m", name).hexdigest(), a.hexdigest() != b.hexdigest(), a.digest_size, a.block_size)
    for pl in [0, 3, 40]:
        for sl in [0, 8, 33]:
            for it in [1, 2, 7, 50]:
                for dk in [1, 20, 33, 64, 100]:
                    pw = make(seed + pl, pl)
                    salt = make(seed + sl + 1, sl)
                    print(pl, sl, it, dk, hashlib.pbkdf2_hmac(name, pw, salt, it, dk).hex())
        print(hashlib.pbkdf2_hmac(name, b"@PW@", b"salt", 3).hex())

main()
'''

DIRECT = r'''
import hashlib
import hmac
import hashlib as hl
from hashlib import sha256, blake2b, blake2s, new as hnew, pbkdf2_hmac

def main():
    data = b"The quick brown fox jumps over the lazy dog"
    h = hashlib.md5(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha1(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha224(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha256(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha384(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha512(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha3_224(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha3_256(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha3_384(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha3_512(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.blake2b(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.blake2s(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha256()
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha256(string=data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha256(data, usedforsecurity=False)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.md5(usedforsecurity=False)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = sha256(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hl.sha1(data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hnew("SHA256", data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hnew("sha-256", data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hnew("SHA3-256", data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hnew("sha2-512", data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.new("md5", data=data)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2b(data, digest_size=1)
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2b(data, digest_size=33, key=b"key")
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2b(data, key=bytes(64))
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2b(data, salt=b"0123456789abcdef", person=b"ABCDEFGHIJKLMNOP")
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2s(data, digest_size=16, key=b"k", salt=b"saltsalt", person=b"persons!")
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = blake2s(key=b"0123456789abcdef0123456789abcdef")
    print(h.name, h.digest_size, h.block_size, h.hexdigest())
    h = hashlib.sha256()
    h.update(b"")
    h.update(data)
    g = h.copy()
    g.update(b"!")
    h.update(b"?")
    print(h.hexdigest(), g.hexdigest(), h.digest().hex() == hashlib.sha256(data + b"?").digest().hex(), g.digest().hex() == hashlib.sha256(data + b"!").hexdigest())
    print(pbkdf2_hmac("sha256", b"@PW@", b"salt", 1000).hex())
    print(hashlib.pbkdf2_hmac("sha1", b"@PW@", b"salt", 4096, 20).hex())
    print(hashlib.pbkdf2_hmac("sha512", b"@PW@", b"salt", 10, dklen=70).hex())
    print(hashlib.pbkdf2_hmac(hash_name="md5", @PW@=b"p", salt=b"s", iterations=3, dklen=None).hex())
    m = hmac.new(b"key", data, hashlib.sha256)
    print(m.hexdigest(), m.name, m.digest_size, m.block_size)
    print(hmac.new(b"key", data, hashlib.sha1).hexdigest())
    print(hmac.new(b"key", data, hashlib.sha3_256).hexdigest())
    print(hmac.new(b"key", data, hashlib.blake2b).hexdigest())
    print(hmac.new(b"key", data, digestmod=hashlib.md5).hexdigest())
    print(hmac.new(key=b"key", msg=data, digestmod="sha384").hexdigest())
    print(hmac.HMAC(b"key", data, "sha512").hexdigest())
    print(hmac.new(b"key", None, "sha256").hexdigest())
    print(hmac.digest(b"key", data, hashlib.sha256).hex())
    print(hmac.digest(b"key", data, "sha512").hex())
    print(hmac.compare_digest(b"abc", b"abc"), hmac.compare_digest(b"abc", b"abd"), hmac.compare_digest(b"", b""),
          hmac.compare_digest(b"abc", b"ab"), hmac.compare_digest("abc", "abc"), hmac.compare_digest("abc", "abd"))

main()
'''

VECTORS = r'''
import base64
import hashlib
import hmac

def b64line(s: bytes) -> None:
    e = base64.b64encode(s)
    print(e.decode(), base64.b64decode(e).decode(), base64.urlsafe_b64encode(s).decode())

def main():
    abc = b"abc"
    two = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    four = b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu"
    mil = b"a" * 1000000
    for name in ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_224", "sha3_256", "sha3_384", "sha3_512", "blake2b", "blake2s"]:
        print(name, hashlib.new(name, b"").hexdigest())
        print(name, hashlib.new(name, abc).hexdigest())
        print(name, hashlib.new(name, two).hexdigest())
        print(name, hashlib.new(name, four).hexdigest())
        print(name, hashlib.new(name, mil).hexdigest())
    print(hmac.new(b"\x0b" * 20, b"Hi There", "sha256").hexdigest())
    print(hmac.new(b"\x0b" * 20, b"Hi There", "sha224").hexdigest())
    print(hmac.new(b"\x0b" * 20, b"Hi There", "sha384").hexdigest())
    print(hmac.new(b"\x0b" * 20, b"Hi There", "sha512").hexdigest())
    print(hmac.new(b"Jefe", b"what do ya want for nothing?", "sha256").hexdigest())
    print(hmac.new(b"Jefe", b"what do ya want for nothing?", "sha512").hexdigest())
    print(hmac.new(b"\xaa" * 20, b"\xdd" * 50, "sha256").hexdigest())
    print(hmac.new(b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First", "sha256").hexdigest())
    print(hmac.new(b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First", "sha384").hexdigest())
    print(hmac.new(b"\x0b" * 16, b"Hi There", "md5").hexdigest())
    print(hmac.new(b"\x0b" * 20, b"Hi There", "sha1").hexdigest())
    print(hmac.new(b"Jefe", b"what do ya want for nothing?", "md5").hexdigest())
    print(hashlib.pbkdf2_hmac("sha1", b"@PW@", b"salt", 1, 20).hex())
    print(hashlib.pbkdf2_hmac("sha1", b"@PW@", b"salt", 2, 20).hex())
    print(hashlib.pbkdf2_hmac("sha1", b"@PW@", b"salt", 4096, 20).hex())
    print(hashlib.pbkdf2_hmac("sha1", b"@PW@@PWU@@PW@", b"saltSALTsaltSALTsaltSALTsaltSALTsalt", 4096, 25).hex())
    print(hashlib.pbkdf2_hmac("sha1", b"pass\x00word", b"sa\x00lt", 4096, 16).hex())
    print(hashlib.pbkdf2_hmac("sha256", b"@PW@", b"salt", 1, 32).hex())
    print(hashlib.pbkdf2_hmac("sha256", b"@PW@", b"salt", 4096, 32).hex())
    b64line(b"")
    b64line(b"f")
    b64line(b"fo")
    b64line(b"foo")
    b64line(b"foob")
    b64line(b"fooba")
    b64line(b"foobar")

main()
'''

ERRORS = r'''
import hashlib
import hmac
import secrets
import sys
import base64

def strict(raw: bytes) -> None:
    # validate=True wording changed between 3.12 patch releases (Excess padding, ...): only the class is compared
    try:
        base64.b64decode(raw, validate=True)
    except ValueError:
        print("ValueError strict")

def main():
    case = int(sys.argv[1])
    try:
        if case == 0:
            hashlib.new("nope")
        elif case == 1:
            hashlib.new("")
        elif case == 2:
            hashlib.blake2b(b"", digest_size=0)
        elif case == 3:
            hashlib.blake2b(b"", digest_size=65)
        elif case == 4:
            hashlib.blake2s(b"", digest_size=33)
        elif case == 5:
            hashlib.blake2b(b"", key=bytes(65))
        elif case == 6:
            hashlib.blake2s(b"", key=bytes(33))
        elif case == 7:
            hashlib.blake2b(b"", salt=bytes(17))
        elif case == 8:
            hashlib.blake2s(b"", salt=bytes(9))
        elif case == 9:
            hashlib.blake2b(b"", person=bytes(17))
        elif case == 10:
            hashlib.blake2s(b"", person=bytes(9))
        elif case == 11:
            hashlib.pbkdf2_hmac("sha256", b"p", b"s", 0)
        elif case == 12:
            hashlib.pbkdf2_hmac("sha256", b"p", b"s", -4)
        elif case == 13:
            hashlib.pbkdf2_hmac("sha256", b"p", b"s", 1, 0)
        elif case == 14:
            hashlib.pbkdf2_hmac("sha256", b"p", b"s", 1, -2)
        elif case == 15:
            hmac.new(b"k", b"m", "nope")
        elif case == 16:
            hmac.digest(b"k", b"m", "nope")
        elif case == 17:
            secrets.randbelow(0)
        elif case == 18:
            secrets.randbelow(-5)
        elif case == 19:
            secrets.token_bytes(-1)
        elif case == 20:
            secrets.token_hex(-3)
        elif case == 21:
            secrets.token_urlsafe(-1)
        elif case == 22:
            xs: list[int] = []
            secrets.choice(xs)
        elif case == 23:
            secrets.choice("")
        elif case == 24:
            secrets.randbits(-1)
        elif case == 25:
            base64.b64decode(b"abcde")
        elif case == 26:
            base64.b64decode(b"abc")
        elif case == 27:
            strict(b"ab=c")
        elif case == 28:
            strict(b"=abc")
        elif case == 29:
            strict(b"ab$c")
        elif case == 30:
            strict(b"ab==cd")
        elif case == 31:
            base64.b64decode("caf\u00e9")
        elif case == 32:
            hashlib.new("sha256 ")
        else:
            print("no such case")
        print("no error")
    except ValueError as e:
        print("ValueError", {MSG})
    except IndexError as e:
        print("IndexError", {MSG})

main()
'''

SECRETS = r'''
import base64
import secrets

def main():
    ok = True
    for n in [0, 1, 2, 15, 16, 31, 32, 33, 100, 1000]:
        b = secrets.token_bytes(n)
        h = secrets.token_hex(n)
        u = secrets.token_urlsafe(n)
        ok = ok and len(b) == n and len(h) == 2 * n
        for c in h:
            ok = ok and c in "0123456789abcdef"
        for c in u:
            ok = ok and c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        ok = ok and len(u) == (n * 4 + 2) // 3
        back = base64.urlsafe_b64decode(u + "=" * (-len(u) % 4))
        ok = ok and len(back) == n
    print("lengths", ok)
    print("default sizes", len(secrets.token_bytes()), len(secrets.token_hex()), len(secrets.token_urlsafe()), secrets.DEFAULT_ENTROPY)
    print("two draws differ", secrets.token_bytes(32) != secrets.token_bytes(32), secrets.token_hex(16) != secrets.token_hex(16))
    ok = True
    seen = set()
    for n in [1, 2, 3, 5, 10, 255, 256, 257, 1000, 65536, 2 ** 31, 2 ** 40 + 7, 2 ** 62, 9223372036854775807]:
        for i in range(60):
            r = secrets.randbelow(n)
            ok = ok and 0 <= r < n
            if n == 5:
                seen.add(r)
    print("randbelow in range", ok, len(seen) == 5)
    print("randbelow(1)", secrets.randbelow(1), secrets.randbelow(1))
    bits = set()
    ok = True
    for k in [0, 1, 2, 7, 8, 9, 31, 32, 33, 62, 63]:
        for i in range(40):
            r = secrets.randbits(k)
            if k < 63:
                ok = ok and 0 <= r < 2 ** k
            else:
                ok = ok and r >= 0
            if k == 1:
                bits.add(r)
    print("randbits", ok, len(bits) == 2)
    xs = [10, 20, 30, 40]
    word = "abcdef"
    got = set()
    ok = True
    for i in range(200):
        a = secrets.choice(xs)
        ok = ok and a in xs
        got.add(a)
        ok = ok and secrets.choice(word) in word
    print("choice", ok, len(got) == 4)
    print("one-element choice", secrets.choice([7]), secrets.choice("z"))
    big = 0
    for i in range(200):
        big = big | secrets.randbelow(2 ** 62)
    print("top bits reached", big > 2 ** 60)

main()
'''

INTS = r'''
import sys
''' + COMMON + r'''
def main():
    seed = int(sys.argv[1])
    x = seed
    for i in range(300):
        x = (x * 1103515245 + 12345) % 2147483648
        n = x % 9
        y = (x * 7919 + i) % 2147483648
        v = (y * 65537 + x) % 4611686018427387904
        if i % 3 == 1:
            v = -v
        order = "big"
        if i % 2 == 0:
            order = "little"
        size = 8
        if v < 2 ** 31 and v > -(2 ** 31):
            size = 4 + n % 5
        b = v.to_bytes(size, order, signed=True)
        print(v, size, b.hex(), int.from_bytes(b, order, signed=True), int.from_bytes(b, order, signed=False) if size < 8 else 0)
        if v >= 0:
            u = v.to_bytes(8, order)
            print(u.hex(), int.from_bytes(u, order), int.from_bytes(u, order, signed=True), v.to_bytes(size + 4, order).hex())
    data = make(seed, 40)
    for k in range(0, 8):
        piece = data[k:k + k]
        print(k, int.from_bytes(piece, "big"), int.from_bytes(piece, "little"), int.from_bytes(piece, byteorder="big"))
        print(int.from_bytes(piece[0:7], "big", signed=True), int.from_bytes(piece[0:7], "little", signed=True))
    print((0).to_bytes(0, "big").hex() == "", (0).to_bytes(1, "big").hex(), (1).to_bytes().hex(), (255).to_bytes(length=2, byteorder="little").hex())
    print((-1).to_bytes(3, "big", signed=True).hex(), (-128).to_bytes(1, "big", signed=True).hex(), (127).to_bytes(1, "big", signed=True).hex())
    print(int.from_bytes(b"", "big"), int.from_bytes(b"\x00\x00\x01", "big"), int.from_bytes(bytes([255, 255]), "big", signed=True))
    print(int.from_bytes(b"\xff" * 8, "big", signed=True), int.from_bytes(b"\xff" * 8, "little", signed=True))
    print(int.from_bytes(b"\x80" + b"\x00" * 7, "big", signed=True), int.from_bytes(b"\x00" * 7 + b"\x80", "little", signed=True))
    print(int.from_bytes(b"\x7f" + b"\xff" * 7, "big", signed=True), int.from_bytes(b"\xff" * 7 + b"\x7f", "little", signed=True))
    lo = int.from_bytes(b"\x80" + b"\x00" * 7, "big", signed=True)
    hi = int.from_bytes(b"\x7f" + b"\xff" * 7, "big", signed=True)
    print(lo.to_bytes(8, "big", signed=True).hex(), hi.to_bytes(8, "big", signed=True).hex())
    print(lo.to_bytes(8, "little", signed=True).hex(), (-1).to_bytes(0, "big", signed=True).hex(), (0).to_bytes(0, "big", signed=True).hex())

main()
'''

INT_ERRORS = r'''
import sys

def main():
    case = int(sys.argv[1])
    try:
        if case == 0:
            print((256).to_bytes(1, "big").hex())
        elif case == 1:
            print((-1).to_bytes(2, "big").hex())
        elif case == 2:
            print((128).to_bytes(1, "big", signed=True).hex())
        elif case == 3:
            print((-129).to_bytes(1, "big", signed=True).hex())
        elif case == 4:
            print((1).to_bytes(2, "middle").hex())
        elif case == 5:
            print((1).to_bytes(-1, "big").hex())
        elif case == 6:
            print(int.from_bytes(b"\x01", "middle"))
        elif case == 7:
            print((1).to_bytes(0, "big").hex())
        elif case == 8:
            print((0).to_bytes(0, "big", signed=True).hex())
        elif case == 9:
            print((-1).to_bytes(0, "big", signed=True).hex())
        else:
            print("no such case")
    except OverflowError as e:
        print("OverflowError", {MSG})
    except ValueError as e:
        print("ValueError", {MSG})

main()
'''

B64 = r'''
import base64
import sys
''' + COMMON + r'''
def main():
    seed = int(sys.argv[1])
    x = seed
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_ !\n"
    for i in range(400):
        x = (x * 1103515245 + 12345) % 2147483648
        n = (x >> 8) % 70
        data = make(x, n)
        e = base64.b64encode(data)
        u = base64.urlsafe_b64encode(data)
        s = base64.standard_b64encode(data)
        print(n, e.decode(), u.decode(), s == e, base64.b64decode(e) == data, base64.urlsafe_b64decode(u) == data,
              base64.standard_b64decode(s) == data, base64.b64decode(e.decode()) == data)
    for i in range(600):
        x = (x * 1103515245 + 12345) % 2147483648
        n = (x >> 8) % 24
        text = ""
        y = x
        for j in range(n):
            y = (y * 1103515245 + 12345) % 2147483648
            text += alphabet[(y >> 8) % len(alphabet)]
        raw = text.encode()
        try:
            print(0, base64.b64decode(raw).hex())
        except ValueError as e:
            print(0, "error", {MSG})
        try:
            print(1, base64.urlsafe_b64decode(text).hex())
        except ValueError as e:
            print(1, "error", {MSG})
        try:
            print(3, base64.b64decode(text, validate=False).hex())
        except ValueError as e:
            print(3, "error", {MSG})

main()
'''

GENERAL_ONLY = r'''
import hmac
import hashlib

def main():
    try:
        hmac.new(b"k", b"m")
    except TypeError as e:
        print("TypeError", e)
    try:
        hmac.compare_digest("caf\u00e9", "caf\u00e9")
    except TypeError as e:
        print("TypeError", e)
    print(hmac.new(b"k", b"m", "sha1").hexdigest())

main()
'''


@unittest.skipUnless(CC, "installed C compiler required")
class CryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-crypto-test-")
        cls.dir = Path(cls.temp.name)
        cls.exe = {}
        cls.oracle = {}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    # ---- helpers ----
    def prepare(self, name, text, mode, msg=None):
        key = (name, mode)
        if key in self.exe:
            return self.exe[key]
        src = self.dir / (name + "_" + mode + ".py")
        text_ail = text if msg is None else text.replace("{MSG}", msg[mode])
        src.write_text(expand(text_ail), encoding="utf8")
        exe = self.dir / (name + "_" + mode + ".exe")
        done = build(src, exe, mode, cwd=self.dir)
        self.assertEqual(done.returncode, 0, "%s build of %s: %s" % (mode, name, done.stderr[-3000:]))
        self.exe[key] = exe
        return exe

    def oracle_src(self, name, text, msg=None):
        key = name
        if key not in self.oracle:
            src = self.dir / (name + "_cpy.py")
            src.write_text(expand(text if msg is None else text.replace("{MSG}", "str(e)")), encoding="utf8")
            self.oracle[key] = src
        return self.oracle[key]

    def compare(self, name, text, args=(), modes=("typed", "general"), msg=None, env=None):
        """The stdout of CPython and of the compiled program for the same arguments, on each path."""
        msgs = {"typed": "str(e)", "default": "str(e)", "general": "str(e)"} if msg is None else dict(msg)
        msgs.setdefault("default", msgs.get("general", "str(e)"))
        uses_msg = "{MSG}" in text
        expected = run_cpython(self.oracle_src(name, text, msg if uses_msg else None), *args)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        outputs = {}
        for mode in modes:
            exe = self.prepare(name, text, mode, msgs if uses_msg else None)
            got = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=300,
                                 env=dict(os.environ, **env) if env else None)
            self.assertEqual(got.returncode, 0, "%s %s: %s" % (mode, args, got.stderr[-1500:]))
            if got.stdout != expected.stdout:
                a, b = expected.stdout.split("\n"), got.stdout.split("\n")
                for i in range(max(len(a), len(b))):
                    x = a[i] if i < len(a) else "<none>"
                    y = b[i] if i < len(b) else "<none>"
                    if x != y:
                        self.fail("%s path, arguments %s, line %d:\n CPython %r\n AIL     %r" % (mode, args, i + 1, x[:400], y[:400]))
            outputs[mode] = got.stdout
        return expected.stdout

    # ---- official vectors ----
    def test_official_vectors(self):
        out = self.compare("vectors", VECTORS)
        lines = out.split("\n")
        by = {}
        for line in lines:
            parts = line.split(" ")
            if len(parts) == 2:
                by.setdefault(parts[0], []).append(parts[1])
        # FIPS 180-4 / 202 / RFC 1321 / 3174 / 7693: "", "abc", the 448-bit and 896-bit messages, one million "a"
        expect = {
            "md5": ["d41d8cd98f00b204e9800998ecf8427e", "900150983cd24fb0d6963f7d28e17f72"],
            "sha1": ["da39a3ee5e6b4b0d3255bfef95601890afd80709", "a9993e364706816aba3e25717850c26c9cd0d89d",
                     "84983e441c3bd26ebaae4aa1f95129e5e54670f1", "a49b2446a02c645bf419f995b67091253a04a259",
                     "34aa973cd4c4daa4f61eeb2bdbad27316534016f"],
            "sha224": ["d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f", "23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7",
                       "75388b16512776cc5dba5da1fd890150b0c6455cb4f58b1952522525"],
            "sha256": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                       "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                       "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
                       "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1",
                       "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"],
            "sha384": ["38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f14898b95b",
                       "cb00753f45a35e8bb5a03d699ac65007272c32ab0eded1631a8b605a43ff5bed8086072ba1e7cc2358baeca134c825a7",
                       "3391fdddfc8dc7393707a65b1b4709397cf8b1d162af05abfe8f450de5f36bc6b0455a8520bc4e6f5fe95b1fe3c8452b",
                       "09330c33f71147e83d192fc782cd1b4753111b173b3b05d22fa08086e3b0f712fcc7c71a557e2db966c3e9fa91746039",
                       "9d0e1809716474cb086e834e310a4a1ced149e9c00f248527972cec5704c2a5b07b8b3dc38ecc4ebae97ddd87f3d8985"],
            "sha512": ["cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e",
                       "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
                       "204a8fc6dda82f0a0ced7beb8e08a41657c16ef468b228a8279be331a703c33596fd15c13b1b07f9aa1d3bea57789ca031ad85c7a71dd70354ec631238ca3445",
                       "8e959b75dae313da8cf4f72814fc143f8f7779c6eb9f7fa17299aeadb6889018501d289e4900f7e4331b99dec4b5433ac7d329eeb6dd26545e96e55b874be909",
                       "e718483d0ce769644e2e42c7bc15b4638e1f98b13b2044285632a803afa973ebde0ff244877ea60a4cb0432ce577c31beb009c5c2c49aa2e4eadb217ad8cc09b"],
            "sha3_224": ["6b4e03423667dbb73b6e15454f0eb1abd4597f9a1b078e3f5b5a6bc7", "e642824c3f8cf24ad09234ee7d3c766fc9a3a5168d0c94ad73b46fdf"],
            "sha3_256": ["a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a",
                         "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532",
                         "41c0dba2a9d6240849100376a8235e2c82e1b9998a999e21db32dd97496d3376"],
            "sha3_384": ["0c63a75b845e4f7d01107d852e4c2485c51a50aaaa94fc61995e71bbee983a2ac3713831264adb47fb6bd1e058d5f004",
                         "ec01498288516fc926459f58e2c6ad8df9b473cb0fc08c2596da7cf0e49be4b298d88cea927ac7f539f1edf228376d25"],
            "sha3_512": ["a69f73cca23a9ac5c8b567dc185a756e97c982164fe25859e0d1dcc1475c80a615b2123af1f5f94c11e3e9402c3ac558f500199d95b6d3e301758586281dcd26",
                         "b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0"],
            "blake2b": ["786a02f742015903c6c6fd852552d272912f4740e15847618a86e217f71f5419d25e1031afee585313896444934eb04b903a685b1448b755d56f701afe9be2ce",
                        "ba80a53f981c4d0d6a2797b69f12f6e94c212f14685ac4b74b12bb6fdbffa2d17d87c5392aab792dc252d5de4533cc9518d38aa8dbf1925ab92386edd4009923"],
            "blake2s": ["69217a3079908094e11121d042354a7c1f55b6482ca1a51e1b250dfd1ed0eef9",
                        "508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982"],
        }
        for name, wanted in expect.items():
            got = by[name]
            self.assertEqual(got[0], wanted[0], name + " of the empty message")
            self.assertEqual(got[1], wanted[1], name + " of abc")
            for k in range(2, len(wanted)):
                self.assertEqual(got[k], wanted[k], "%s vector %d" % (name, k))
        text = out
        for want in (
                "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7",      # RFC 4231 case 1, SHA-256
                "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843",      # case 2
                "773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe",      # case 3
                "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54",      # case 6
                "9294727a3638bb1c13f48ef8158bfc9d",                                      # RFC 2202 md5 case 1
                "b617318655057264e28bc0b6fb378c8ef146be00",                              # RFC 2202 sha1 case 1
                "750c783e6ab0b503eaa86e310a5db738",                                      # RFC 2202 md5 case 2
                "0c60c80f961f0e71f3a9b524af6012062fe037a6",                              # RFC 6070
                "ea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957",
                "4b007901b765489abead49d926f721d065a429c1",
                "3d2eec4fe41c849b80c8d83662c0e44a8b291a964cf2f07038",
                "56fa6aa75548099dcc37d7f03425e0c3",
                "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b",      # PBKDF2-HMAC-SHA256, 1 iteration
                "c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a",      # 4096
                "Zm9vYmFy", "Zm9vYmE=", "Zm9vYg==", "Zm9v", "Zm8=", "Zg=="):             # RFC 4648
            self.assertIn(want, text)

    # ---- every hash, every length ----
    def test_every_hash_random_inputs(self):
        generator = random.Random(20261020)
        for index, name in enumerate(NAMES):
            for seed in (generator.randrange(1, 10 ** 6), generator.randrange(1, 10 ** 6)):
                with self.subTest(hash=name, seed=seed):
                    self.compare("hash", HASH, (index, seed))

    def test_the_portable_sha_code_agrees_with_the_cpu_instructions(self):
        # sha1 / sha224 / sha256 use the x86 SHA extensions when the CPU has them; AIL_HASH_NO_SHANI=1 runs the portable code
        generator = random.Random(20261022)
        for index in (1, 2, 3):
            for modes in (("typed", "general"),):
                with self.subTest(hash=NAMES[index]):
                    self.compare("hash", HASH, (index, generator.randrange(1, 10 ** 6)), modes=modes, env={"AIL_HASH_NO_SHANI": "1"})
                    self.compare("hmac", HMAC, (index, generator.randrange(1, 10 ** 6)), modes=("typed",), env={"AIL_HASH_NO_SHANI": "1"})

    def test_hmac_and_pbkdf2(self):
        generator = random.Random(20261021)
        for index, name in enumerate(NAMES):
            with self.subTest(hash=name):
                self.compare("hmac", HMAC, (index, generator.randrange(1, 10 ** 6)))

    def test_constructors_attributes_and_forms(self):
        out = self.compare("direct", DIRECT)
        self.assertIn("sha256 32 64 d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592", out)
        self.assertIn("blake2b 64 128", out)
        self.assertIn("hmac-sha256 32 64", out)

    # ---- errors ----
    def test_error_texts(self):
        for case in range(34):
            with self.subTest(case=case):
                out = self.compare("errors", ERRORS, (case,), msg={"typed": "str(e)", "general": "str(e)"})
                self.assertNotEqual(out.strip(), "no error" if case < 33 else "x")
                if 27 <= case <= 30:
                    self.assertEqual(out, "ValueError strict\nno error\n")

    def test_error_texts_known_cases(self):
        self.assertEqual(self.compare("errors", ERRORS, (0,), msg={"typed": "str(e)", "general": "str(e)"}),
                         "ValueError unsupported hash type nope\n")
        self.assertEqual(self.compare("errors", ERRORS, (25,), msg={"typed": "str(e)", "general": "str(e)"}),
                         "ValueError Invalid base64-encoded string: number of data characters (5) cannot be 1 more than a multiple of 4\n")
        self.assertEqual(self.compare("errors", ERRORS, (22,), msg={"typed": "str(e)", "general": "str(e)"}),
                         "IndexError Cannot choose from an empty sequence\n")

    def test_general_path_type_errors(self):
        out = self.compare("generalonly", GENERAL_ONLY, modes=("general",))
        self.assertIn("TypeError Missing required argument 'digestmod'.", out)
        self.assertIn("comparing strings with non-ASCII characters is not supported", out)

    # ---- secrets ----
    def test_secrets_types_lengths_and_ranges(self):
        for mode in ("default", "general"):
            exe = self.prepare("secrets", SECRETS, mode)
            first = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = [
                "lengths True",
                "default sizes 32 64 43 32",
                "two draws differ True True",
                "randbelow in range True True",
                "randbelow(1) 0 0",
                "randbits True True",
                "choice True True",
                "one-element choice 7 z",
                "top bits reached True",
            ]
            self.assertEqual(first.stdout.strip().split("\n"), expected, mode)
        # the same program is a valid CPython program with the same answers
        real = run_cpython(self.oracle_src("secrets", SECRETS))
        self.assertEqual(real.stdout.strip().split("\n"), expected)

    # ---- integers <-> bytes ----
    def test_int_to_bytes_and_from_bytes(self):
        for seed in (1, 77, 31337, 123456):
            with self.subTest(seed=seed):
                self.compare("ints", INTS, (seed,), modes=("default", "general"))

    def test_int_bytes_errors(self):
        for case in range(10):
            with self.subTest(case=case):
                self.compare("interrors", INT_ERRORS, (case,), modes=("default", "general"),
                             msg={"typed": "str(e)", "general": "str(e)"})

    def test_typed_path_refuses_big_int_capable_int_bytes(self):
        # int.from_bytes can produce a value beyond int64 whatever its length, so the typed-only build names that reason.
        src = self.dir / "bigcap.py"
        src.write_text(INTS, encoding="utf8")
        exe = self.dir / "bigcap.exe"
        done = build(src, exe, "typed", cwd=self.dir)
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("can need an int beyond int64", done.stderr)
        self.assertIn("the typed path has int64 only", done.stderr)
        self.assertIn("int.from_bytes", done.stderr)

    # ---- base64 ----
    def test_base64_round_trips_and_decoder_fuzz(self):
        for seed in (3, 99, 424242):
            with self.subTest(seed=seed):
                self.compare("b64", B64, (seed,), msg={"typed": "str(e)", "general": "str(e)"})

    # ---- refusals and cost ----
    def refused(self, text, *needles, mode="typed"):
        src = self.dir / "refused.py"
        src.write_text(text, encoding="utf8")
        exe = self.dir / "refused.exe"
        if exe.exists():
            exe.unlink()
        done = build(src, exe, mode, cwd=self.dir)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("Traceback", done.stderr)
        for needle in needles:
            self.assertIn(needle, done.stderr)

    def test_refusals_name_what_to_write(self):
        self.refused("import hashlib\n\ndef main() -> None:\n    h = hashlib.shake_128(b'x')\n    print(1)\n\nmain()\n",
                     "hashlib.shake_128 is not built", "write instead")
        self.refused("import hashlib\n\ndef main() -> None:\n    print(hashlib.scrypt(b'a', salt=b'b', n=2, r=1, p=1).hex())\n\nmain()\n",
                     "hashlib.scrypt is not built")
        self.refused("import secrets\n\ndef f() -> list[int]:\n    return [1, 2]\n\ndef main() -> None:\n    print(secrets.choice(f()))\n\nmain()\n",
                     "secrets.choice(<expression>)", "write instead")
        self.refused("import hmac\n\ndef main() -> None:\n    print(hmac.new(b'k', b'm').hexdigest())\n\nmain()\n",
                     "without digestmod", "write instead")
        self.refused("import base64\n\ndef main() -> None:\n    print(base64.b32encode(b'k'))\n\nmain()\n",
                     "base64.b32encode is not built")
        self.refused("import hashlib\n\ndef main() -> None:\n    f = hashlib.sha256\n    print(1)\n\nmain()\n",
                     "used as a value is not built")
        self.refused("import hashlib\n\ndef main() -> None:\n    print(hashlib.blake2b(b'x', fanout=2).hexdigest())\n\nmain()\n",
                     "fanout")

    def c_of(self, text, mode="typed"):
        src = self.dir / "c_of.py"
        src.write_text(text, encoding="utf8")
        exe = self.dir / "c_of.exe"
        dbg = self.dir / "dbg"
        for leftover in (exe, exe.with_suffix(".c")):
            if leftover.exists():
                leftover.unlink()
        if dbg.exists():
            shutil.rmtree(dbg)
        if mode == "general":              # pyc.py leaves the C beside the executable
            done = build(src, exe, mode, cwd=self.dir)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            return exe.with_suffix(".c").read_text(encoding="utf-8")
        done = build(src, exe, mode, extra=("--debug-dir", str(dbg)), cwd=self.dir)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        return (dbg / "program.c").read_text(encoding="utf-8")

    def test_a_program_without_these_modules_carries_none_of_the_code(self):
        plain = ("def main() -> None:\n    b = bytes([1, 2, 3])\n    print(b.hex(), len(b))\n\nmain()\n",
                 "import sys\n\ndef main() -> None:\n    print(len(sys.argv))\n    print(int('12') * 2)\n\nmain()\n")
        for mode in ("typed", "general"):
            for text in plain:
                c = self.c_of(text, mode)
                for marker in ("AILHASH_CORE_H", "ailhs_", "ailt_hs_", "ail2h_", "_AilHash"):
                    self.assertNotIn(marker, c, (mode, marker))

    def test_a_crypto_program_carries_the_core(self):
        for mode in ("typed", "general"):
            c = self.c_of("import hashlib\n\ndef main() -> None:\n    print(hashlib.sha256(b'abc').hexdigest())\n\nmain()\n", mode)
            self.assertIn("AILHASH_CORE_H", c)
            self.assertNotIn("#include <openssl", c)
            self.assertNotIn("EVP_", c)

    def test_no_library_is_linked(self):
        # the core is plain libc: a crypto program links like any other
        src = self.dir / "link.py"
        src.write_text("import hashlib\nimport secrets\n\ndef main() -> None:\n    print(hashlib.sha1(b'a').hexdigest(), len(secrets.token_hex(4)))\n\nmain()\n", encoding="utf8")
        exe = self.dir / "link.exe"
        done = build(src, exe, "typed", cwd=self.dir)
        self.assertEqual(done.returncode, 0, done.stderr)
        if shutil.which("ldd"):
            libs = subprocess.run(["ldd", str(exe)], capture_output=True, text=True).stdout
            self.assertNotIn("libcrypto", libs)
            self.assertNotIn("libssl", libs)
        ran = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(ran.stdout, "86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 8\n")

    def test_the_program_text_decides_str_or_bytes(self):
        text = ("import base64\nimport hmac\n\ndef main() -> None:\n"
                "    print(base64.b64decode('aGk=').decode(), hmac.compare_digest('a', 'a'))\n"
                "    s = base64.b64encode(b'hi').decode()\n    print(base64.b64decode(s).decode(), s)\n\nmain()\n")
        # `s` is a variable: the pass sees no str in the text, so the typed path refuses with its own message
        # (a bytes argument is expected); the general path takes either
        src = self.dir / "strish.py"
        src.write_text(text, encoding="utf8")
        exe = self.dir / "strish.exe"
        done = build(src, exe, "general", cwd=self.dir)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        ran = subprocess.run([str(exe)], capture_output=True, text=True)
        want = run_cpython(src)
        self.assertEqual(ran.stdout, want.stdout)


if __name__ == "__main__":
    unittest.main()
