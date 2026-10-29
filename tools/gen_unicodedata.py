"""Generate python/pkg-v12/prelude_unicodedata.py from the running CPython's unicodedata.

    python3 tools/gen_unicodedata.py

The generated module is plain Python in the subset the compiler builds: category ranges, the canonical
decomposition / combining-class / composition tables of Unicode 15.0, and a front-coded name table (Hangul
syllables and the ideograph ranges are computed by rule). The data is CPython 3.12's own, so the supported
functions (`name`, `category`, `normalize` for NFC/NFD) agree with it; everything else stays refused.
"""
import sys
import unicodedata as u
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'AIL_CURRENT/python/pkg-v12/prelude_unicodedata.py'
MAX_CATEGORY_RANGES = 5000


def q(text):
    return ascii(text)


def lines(values, per=8):
    out = []
    for i in range(0, len(values), per):
        out.append('    ' + ', '.join(values[i:i + per]) + ',')
    return '\n'.join(out)


def category_ranges():
    ranges, start, prev = [], 0, None
    for cp in range(0x110000):
        cat = u.category(chr(cp))
        if cat != prev:
            if prev is not None:
                ranges.append((start, cp - 1, prev))
            start, prev = cp, cat
    ranges.append((start, 0x10FFFF, prev))
    assert len(ranges) <= MAX_CATEGORY_RANGES, len(ranges)
    return ranges


def combining_ranges():
    ranges, start, last = [], None, 0
    for cp in range(0x110000):
        value = u.combining(chr(cp))
        if value:
            if start is None:
                start, last = cp, value
            elif value != last:
                ranges.append((start, cp - 1, last))
                start, last = cp, value
        elif start is not None:
            ranges.append((start, cp - 1, last))
            start = None
    if start is not None:
        ranges.append((start, 0x10FFFF, last))
    return ranges


def decompositions():
    table = {}
    for cp in range(0x10000):
        if 0xAC00 <= cp <= 0xD7A3:
            continue
        ch = chr(cp)
        nfd = u.normalize('NFD', ch)
        # Seven CJK compatibility ideographs decompose to a non-BMP code point (U+FA6C -> U+242EE
        # and six more); the 16-bit v2 runtime cannot hold those, so they stay undecomposed here and
        # are a recorded limitation, not a silent different answer for ordinary text.
        if nfd != ch and all(ord(c) <= 0xFFFF for c in nfd):
            table[cp] = nfd
    return table


def compositions():
    pairs = {}
    for cp in range(0x110000):
        raw = u.decomposition(chr(cp))
        if not raw or raw.startswith('<'):
            continue
        parts = raw.split()
        if len(parts) != 2:
            continue
        a, b = int(parts[0], 16), int(parts[1], 16)
        if u.normalize('NFC', chr(a) + chr(b)) == chr(cp):
            pairs[(a, b)] = cp
    return pairs


def algorithmic_names():
    """(start, end, prefix) where name(cp) == prefix + uppercase hex(cp), minimum four digits."""
    hits = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF or 0xAC00 <= cp <= 0xD7A3:
            continue
        try:
            name = u.name(chr(cp))
        except ValueError:
            continue
        suffix = '%04X' % cp
        if name.endswith(suffix) and len(name) > len(suffix):
            hits.append((cp, name[:-len(suffix)]))
    ranges = []
    if hits:
        start = previous = hits[0][0]
        prefix = hits[0][1]
        for cp, pref in hits[1:]:
            if cp == previous + 1 and pref == prefix:
                previous = cp
            else:
                ranges.append((start, previous, prefix))
                start = previous = cp
                prefix = pref
        ranges.append((start, previous, prefix))
    return ranges


def names_table():
    rows = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF or 0xAC00 <= cp <= 0xD7A3:
            continue
        try:
            name = u.name(chr(cp))
        except ValueError:
            continue
        suffix = '%04X' % cp
        if name.endswith(suffix) and len(name) > len(suffix):
            continue
        rows.append((cp, name))
    data = bytearray()
    previous = ''
    for cp, name in rows:
        prefix = 0
        while prefix < min(len(previous), len(name)) and previous[prefix] == name[prefix]:
            prefix += 1
        suffix = name[prefix:].encode('utf-8')
        data += cp.to_bytes(3, 'big')
        data.append(prefix)
        data.append(len(suffix))
        data += suffix
        previous = name
    return bytes(data), len(rows)


def as_hex(data):
    text = bytes(data).hex().upper()
    chunks = [text[i:i + 8000] for i in range(0, len(text), 8000)]
    return '(\n' + '\n'.join('    ' + q(chunk) for chunk in chunks) + '\n)'


def encode_category(ranges):
    data = bytearray()
    for first, last, name in ranges:
        data += first.to_bytes(3, 'big') + last.to_bytes(3, 'big') + name.encode('ascii')
    return data


def encode_ccc(ranges):
    data = bytearray()
    for first, last, value in ranges:
        data += first.to_bytes(3, 'big') + last.to_bytes(3, 'big') + bytes([value])
    return data


def encode_decomp(table):
    # Code points, not UTF-8: an astral decomposition value must not go through bytes.decode() in the
    # 16-bit v2 runtime (it refuses a decoded code point above U+FFFF); chr() builds it directly.
    data = bytearray()
    for cp, value in sorted(table.items()):
        data += cp.to_bytes(3, 'big') + bytes([len(value)])
        for ch in value:
            data += ord(ch).to_bytes(3, 'big')
    return data


def encode_compose(table):
    data = bytearray()
    for (a, b), cp in sorted(table.items()):
        data += a.to_bytes(3, 'big') + b.to_bytes(3, 'big') + cp.to_bytes(3, 'big')
    return data


def main():
    categories = category_ranges()
    combining = combining_ranges()
    decomp = decompositions()
    comp = compositions()
    alg = algorithmic_names()
    data, count = names_table()
    hexed = data.hex().upper()
    chunks = [hexed[i:i + 4000] for i in range(0, len(hexed), 4000)]
    text = '''# -*- coding: utf-8 -*-
# prelude_unicodedata.py -- `unicodedata` as Python source (smalllib5.py injects it when a program imports
# the module). Generated by tools/gen_unicodedata.py from CPython @PY@ (Unicode @UNI@): category ranges,
# canonical decomposition / combining class / composition tables, and a front-coded name table. Hangul
# syllables and the ideograph ranges are computed by rule. The built names are `name`, `category`,
# `normalize` (NFC and NFD only) and the constant `unidata_version`; every other name is refused.

_AIL_UNI_VERSION = @VERSION@
_AIL_UNI_NODEFAULT = []

_AIL_UNI_NAME_RANGES = [
@RANGES@
]

_AIL_UNI_NAME_CHUNKS = [
@CHUNKS@
]


def _ail_uni_decode_ranges(text, width: int):
    data = bytes.fromhex(text)
    out = []
    i = 0
    while i < len(data):
        first = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        last = (data[i + 3] << 16) | (data[i + 4] << 8) | data[i + 5]
        value = data[i + 6:i + 6 + width].decode("ascii")
        out.append((first, last, value))
        i = i + 6 + width
    return out


def _ail_uni_decode_ccc(text):
    data = bytes.fromhex(text)
    out = []
    i = 0
    while i < len(data):
        first = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        last = (data[i + 3] << 16) | (data[i + 4] << 8) | data[i + 5]
        out.append((first, last, data[i + 6]))
        i = i + 7
    return out


def _ail_uni_decode_decomp(text):
    data = bytes.fromhex(text)
    out = {}
    i = 0
    while i < len(data):
        cp = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        length = data[i + 3]
        i = i + 4
        value = ""
        k = 0
        while k < length:
            point = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
            value = value + chr(point)
            i = i + 3
            k = k + 1
        out[cp] = value
    return out


def _ail_uni_decode_compose(text):
    data = bytes.fromhex(text)
    out = {}
    i = 0
    while i < len(data):
        a = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        b = (data[i + 3] << 16) | (data[i + 4] << 8) | data[i + 5]
        cp = (data[i + 6] << 16) | (data[i + 7] << 8) | data[i + 8]
        out[(a, b)] = cp
        i = i + 9
    return out


_AIL_UNI_CATEGORY = _ail_uni_decode_ranges(@CATEGORY@, 2)

_AIL_UNI_CCC = _ail_uni_decode_ccc(@CCC@)

_AIL_UNI_DECOMP = _ail_uni_decode_decomp(@DECOMP@)

_AIL_UNI_COMPOSE = _ail_uni_decode_compose(@COMPOSE@)

def _ail_uni_tname(x) -> str:
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, bytes):
        return "bytes"
    if isinstance(x, list):
        return "list"
    if isinstance(x, dict):
        return "dict"
    if isinstance(x, tuple):
        return "tuple"
    if x is None:
        return "None"
    return "object"


def _ail_uni_point(ch, what: str, numbered: bool = False) -> int:
    label = what + (" argument 1" if numbered else " argument")
    if not isinstance(ch, str):
        raise TypeError(label + " must be a unicode character, not " + _ail_uni_tname(ch))
    if len(ch) != 1:
        raise TypeError(label + " must be a unicode character, not str")
    return ord(ch)


def _ail_uni_hex4(n: int) -> str:
    digits = "0123456789ABCDEF"
    out = ""
    if n == 0:
        out = "0"
    while n > 0:
        out = digits[n % 16] + out
        n = n // 16
    while len(out) < 4:
        out = "0" + out
    return out


def _ail_uni_category(ch) -> str:
    cp = _ail_uni_point(ch, "category()")
    lo = 0
    hi = len(_AIL_UNI_CATEGORY) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        first, last, name = _AIL_UNI_CATEGORY[mid]
        if cp < first:
            hi = mid - 1
        elif cp > last:
            lo = mid + 1
        else:
            return name
    return "Cn"


def _ail_uni_ccc(cp: int) -> int:
    lo = 0
    hi = len(_AIL_UNI_CCC) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        first, last, value = _AIL_UNI_CCC[mid]
        if cp < first:
            hi = mid - 1
        elif cp > last:
            lo = mid + 1
        else:
            return value
    return 0


def _ail_uni_decode_names():
    data = bytes.fromhex("".join(_AIL_UNI_NAME_CHUNKS))
    codes = []
    names = []
    i = 0
    previous = ""
    while i < len(data):
        cp = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        i = i + 3
        prefix = data[i]
        length = data[i + 1]
        i = i + 2
        suffix = data[i:i + length].decode("utf-8")
        i = i + length
        name = previous[:prefix] + suffix
        codes.append(cp)
        names.append(name)
        previous = name
    return codes, names


_AIL_UNI_NAMES_PAIR = _ail_uni_decode_names()


def _ail_uni_name(ch, default=_AIL_UNI_NODEFAULT):
    cp = _ail_uni_point(ch, "name()", True)
    if 0xAC00 <= cp <= 0xD7A3:
        return "HANGUL SYLLABLE " + _ail_uni_hangul_name(cp)
    for first, last, prefix in _AIL_UNI_NAME_RANGES:
        if first <= cp <= last:
            return prefix + _ail_uni_hex4(cp)
    codes = _AIL_UNI_NAMES_PAIR[0]
    names = _AIL_UNI_NAMES_PAIR[1]
    lo = 0
    hi = len(codes) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        at = codes[mid]
        if cp < at:
            hi = mid - 1
        elif cp > at:
            lo = mid + 1
        else:
            return names[mid]
    if default is _AIL_UNI_NODEFAULT:
        raise ValueError("no such name")
    return default


_AIL_UNI_L_NAMES = ["G", "GG", "N", "D", "DD", "R", "M", "B", "BB", "S", "SS", "", "J", "JJ", "C", "K", "T", "P", "H"]
_AIL_UNI_V_NAMES = ["A", "AE", "YA", "YAE", "EO", "E", "YEO", "YE", "O", "WA", "WAE", "OE", "YO", "U", "WEO", "WE", "WI", "YU", "EU", "YI", "I"]
_AIL_UNI_T_NAMES = ["", "G", "GG", "GS", "N", "NJ", "NH", "D", "L", "LG", "LM", "LB", "LS", "LT", "LP", "LH", "M", "B", "BS", "S", "SS", "NG", "J", "C", "K", "T", "P", "H"]


def _ail_uni_hangul_name(cp: int) -> str:
    index = cp - 0xAC00
    lead = index // 588
    vowel = (index % 588) // 28
    trail = index % 28
    return _AIL_UNI_L_NAMES[lead] + _AIL_UNI_V_NAMES[vowel] + _AIL_UNI_T_NAMES[trail]


def _ail_uni_hangul_decompose(cp: int) -> str:
    index = cp - 0xAC00
    lead = 0x1100 + index // 588
    vowel = 0x1161 + (index % 588) // 28
    trail = index % 28
    if trail == 0:
        return chr(lead) + chr(vowel)
    return chr(lead) + chr(vowel) + chr(0x11A7 + trail)


def _ail_uni_decompose_one(cp: int) -> str:
    if 0xAC00 <= cp <= 0xD7A3:
        return _ail_uni_hangul_decompose(cp)
    got = _AIL_UNI_DECOMP.get(cp)
    if got is not None:
        return got
    return chr(cp)


def _ail_uni_nfd(text: str) -> str:
    units = []
    for ch in text:
        units.extend(_ail_uni_decompose_one(ord(ch)))
    i = 0
    while i < len(units):
        if _ail_uni_ccc(ord(units[i])) == 0:
            i = i + 1
            continue
        j = i
        while j < len(units) and _ail_uni_ccc(ord(units[j])) != 0:
            j = j + 1
        k = i + 1
        while k < j:
            value = units[k]
            value_ccc = _ail_uni_ccc(ord(value))
            m = k - 1
            while m >= i and _ail_uni_ccc(ord(units[m])) > value_ccc:
                units[m + 1] = units[m]
                m = m - 1
            units[m + 1] = value
            k = k + 1
        i = j
    return "".join(units)


def _ail_uni_compose_pair(a: str, b: str):
    acp = ord(a)
    bcp = ord(b)
    if 0x1100 <= acp <= 0x1112 and 0x1161 <= bcp <= 0x1175:
        return chr(0xAC00 + ((acp - 0x1100) * 21 + (bcp - 0x1161)) * 28)
    if 0xAC00 <= acp <= 0xD7A3 and (acp - 0xAC00) % 28 == 0 and 0x11A8 <= bcp <= 0x11C2:
        return chr(acp + (bcp - 0x11A7))
    pair = _AIL_UNI_COMPOSE.get((acp, bcp))
    if pair is None:
        return None
    return chr(pair)


def _ail_uni_nfc(text: str) -> str:
    units = list(_ail_uni_nfd(text))
    out = []
    starter = -1
    last_ccc = 0
    for ch in units:
        ccc = _ail_uni_ccc(ord(ch))
        if starter >= 0 and (last_ccc == 0 or last_ccc < ccc):
            combined = _ail_uni_compose_pair(out[starter], ch)
            if combined is not None:
                out[starter] = combined
                continue
        if ccc == 0:
            starter = len(out)
        last_ccc = ccc
        out.append(ch)
    return "".join(out)


def _ail_uni_normalize(form, unistr):
    if not isinstance(form, str):
        raise TypeError("normalize() argument 1 must be str, not " + _ail_uni_tname(form))
    if not isinstance(unistr, str):
        raise TypeError("normalize() argument 2 must be str, not " + _ail_uni_tname(unistr))
    if form == "NFC":
        return _ail_uni_nfc(unistr)
    if form == "NFD":
        return _ail_uni_nfd(unistr)
    raise ValueError("invalid normalization form")
'''
    text = (text.replace('@PY@', sys.version.split()[0]).replace('@UNI@', u.unidata_version)
            .replace('@VERSION@', q(u.unidata_version))
            .replace('@CATEGORY@', as_hex(encode_category(categories)))
            .replace('@CCC@', as_hex(encode_ccc(combining)))
            .replace('@DECOMP@', as_hex(encode_decomp(decomp)))
            .replace('@COMPOSE@', as_hex(encode_compose(comp)))
            .replace('@RANGES@', lines(['(%d, %d, %s)' % (row[0], row[1], q(row[2])) for row in alg]))
            .replace('@CHUNKS@', lines([q(chunk) for chunk in chunks], per=1)))
    OUT.write_text(text, encoding='utf-8')
    print('wrote %s: %d bytes, %d names, %d categories, %d ccc, %d decompositions, %d pairs'
          % (OUT.name, len(text), count, len(categories), len(combining), len(decomp), len(comp)))


if __name__ == '__main__':
    main()
