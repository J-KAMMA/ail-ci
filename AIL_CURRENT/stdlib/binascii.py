"""G5a: the stdlib `binascii` module (hex, base64, crc32, crc_hqx) for AIL.

`import binascii` in a program compiled by AIL finds this file when the program's own directory
has no `binascii.py` (ail_modules.py searches the bundled `stdlib/` last).  The behaviour follows
CPython 3.12's `binascii` (written in C), including the exact `binascii.Error` texts.

Supported: hexlify / b2a_hex (with `sep` and `bytes_per_sep`), unhexlify / a2b_hex, b2a_base64,
a2b_base64 (with `strict_mode`), crc32 (table-driven, polynomial 0xEDB88320) and crc_hqx (CCITT,
polynomial 0x1021).  `bytes`, `bytearray` and, where CPython does, an ASCII `str` are accepted.

Not provided: b2a_uu, a2b_uu, b2a_qp, a2b_qp.
"""

_HEX = "0123456789abcdef"
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class Error(ValueError):
    pass


class Incomplete(Exception):
    pass


def _ascii_bytes(data):
    if isinstance(data, str):
        out = bytearray()
        i = 0
        while i < len(data):
            c = ord(data[i])
            if c > 127:
                raise ValueError("string argument should contain only ASCII characters")
            out.append(c)
            i = i + 1
        return bytes(out)
    return bytes(data)


def _hex_value(c):
    if c >= 48 and c <= 57:
        return c - 48
    if c >= 65 and c <= 70:
        return c - 55
    if c >= 97 and c <= 102:
        return c - 87
    return -1


def _b64_value(c):
    if c >= 65 and c <= 90:
        return c - 65
    if c >= 97 and c <= 122:
        return c - 71
    if c >= 48 and c <= 57:
        return c + 4
    if c == 43:
        return 62
    if c == 47:
        return 63
    return -1


_CRC32_TABLE = [
    0x00000000, 0x77073096, 0xEE0E612C, 0x990951BA, 0x076DC419, 0x706AF48F, 0xE963A535, 0x9E6495A3,
    0x0EDB8832, 0x79DCB8A4, 0xE0D5E91E, 0x97D2D988, 0x09B64C2B, 0x7EB17CBD, 0xE7B82D07, 0x90BF1D91,
    0x1DB71064, 0x6AB020F2, 0xF3B97148, 0x84BE41DE, 0x1ADAD47D, 0x6DDDE4EB, 0xF4D4B551, 0x83D385C7,
    0x136C9856, 0x646BA8C0, 0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9, 0xFA0F3D63, 0x8D080DF5,
    0x3B6E20C8, 0x4C69105E, 0xD56041E4, 0xA2677172, 0x3C03E4D1, 0x4B04D447, 0xD20D85FD, 0xA50AB56B,
    0x35B5A8FA, 0x42B2986C, 0xDBBBC9D6, 0xACBCF940, 0x32D86CE3, 0x45DF5C75, 0xDCD60DCF, 0xABD13D59,
    0x26D930AC, 0x51DE003A, 0xC8D75180, 0xBFD06116, 0x21B4F4B5, 0x56B3C423, 0xCFBA9599, 0xB8BDA50F,
    0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924, 0x2F6F7C87, 0x58684C11, 0xC1611DAB, 0xB6662D3D,
    0x76DC4190, 0x01DB7106, 0x98D220BC, 0xEFD5102A, 0x71B18589, 0x06B6B51F, 0x9FBFE4A5, 0xE8B8D433,
    0x7807C9A2, 0x0F00F934, 0x9609A88E, 0xE10E9818, 0x7F6A0DBB, 0x086D3D2D, 0x91646C97, 0xE6635C01,
    0x6B6B51F4, 0x1C6C6162, 0x856530D8, 0xF262004E, 0x6C0695ED, 0x1B01A57B, 0x8208F4C1, 0xF50FC457,
    0x65B0D9C6, 0x12B7E950, 0x8BBEB8EA, 0xFCB9887C, 0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xFBD44C65,
    0x4DB26158, 0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541, 0x3DD895D7, 0xA4D1C46D, 0xD3D6F4FB,
    0x4369E96A, 0x346ED9FC, 0xAD678846, 0xDA60B8D0, 0x44042D73, 0x33031DE5, 0xAA0A4C5F, 0xDD0D7CC9,
    0x5005713C, 0x270241AA, 0xBE0B1010, 0xC90C2086, 0x5768B525, 0x206F85B3, 0xB966D409, 0xCE61E49F,
    0x5EDEF90E, 0x29D9C998, 0xB0D09822, 0xC7D7A8B4, 0x59B33D17, 0x2EB40D81, 0xB7BD5C3B, 0xC0BA6CAD,
    0xEDB88320, 0x9ABFB3B6, 0x03B6E20C, 0x74B1D29A, 0xEAD54739, 0x9DD277AF, 0x04DB2615, 0x73DC1683,
    0xE3630B12, 0x94643B84, 0x0D6D6A3E, 0x7A6A5AA8, 0xE40ECF0B, 0x9309FF9D, 0x0A00AE27, 0x7D079EB1,
    0xF00F9344, 0x8708A3D2, 0x1E01F268, 0x6906C2FE, 0xF762575D, 0x806567CB, 0x196C3671, 0x6E6B06E7,
    0xFED41B76, 0x89D32BE0, 0x10DA7A5A, 0x67DD4ACC, 0xF9B9DF6F, 0x8EBEEFF9, 0x17B7BE43, 0x60B08ED5,
    0xD6D6A3E8, 0xA1D1937E, 0x38D8C2C4, 0x4FDFF252, 0xD1BB67F1, 0xA6BC5767, 0x3FB506DD, 0x48B2364B,
    0xD80D2BDA, 0xAF0A1B4C, 0x36034AF6, 0x41047A60, 0xDF60EFC3, 0xA867DF55, 0x316E8EEF, 0x4669BE79,
    0xCB61B38C, 0xBC66831A, 0x256FD2A0, 0x5268E236, 0xCC0C7795, 0xBB0B4703, 0x220216B9, 0x5505262F,
    0xC5BA3BBE, 0xB2BD0B28, 0x2BB45A92, 0x5CB36A04, 0xC2D7FFA7, 0xB5D0CF31, 0x2CD99E8B, 0x5BDEAE1D,
    0x9B64C2B0, 0xEC63F226, 0x756AA39C, 0x026D930A, 0x9C0906A9, 0xEB0E363F, 0x72076785, 0x05005713,
    0x95BF4A82, 0xE2B87A14, 0x7BB12BAE, 0x0CB61B38, 0x92D28E9B, 0xE5D5BE0D, 0x7CDCEFB7, 0x0BDBDF21,
    0x86D3D2D4, 0xF1D4E242, 0x68DDB3F8, 0x1FDA836E, 0x81BE16CD, 0xF6B9265B, 0x6FB077E1, 0x18B74777,
    0x88085AE6, 0xFF0F6A70, 0x66063BCA, 0x11010B5C, 0x8F659EFF, 0xF862AE69, 0x616BFFD3, 0x166CCF45,
    0xA00AE278, 0xD70DD2EE, 0x4E048354, 0x3903B3C2, 0xA7672661, 0xD06016F7, 0x4969474D, 0x3E6E77DB,
    0xAED16A4A, 0xD9D65ADC, 0x40DF0B66, 0x37D83BF0, 0xA9BCAE53, 0xDEBB9EC5, 0x47B2CF7F, 0x30B5FFE9,
    0xBDBDF21C, 0xCABAC28A, 0x53B39330, 0x24B4A3A6, 0xBAD03605, 0xCDD70693, 0x54DE5729, 0x23D967BF,
    0xB3667A2E, 0xC4614AB8, 0x5D681B02, 0x2A6F2B94, 0xB40BBE37, 0xC30C8EA1, 0x5A05DF1B, 0x2D02EF8D,
]


def hexlify(data: bytes, sep: bytes = b"", bytes_per_sep: int = 1) -> bytes:
    buf = _ascii_bytes(data)
    out = bytearray()
    sepc = -1
    if len(sep) != 0:
        if isinstance(sep, str):
            if len(sep) != 1:
                raise ValueError("sep must be length 1.")
            sepc = ord(sep)
        else:
            sb = bytes(sep)
            if len(sb) != 1:
                raise ValueError("sep must be length 1.")
            sepc = sb[0]
    n = len(buf)
    i = 0
    while i < n:
        if sepc >= 0 and i > 0 and bytes_per_sep != 0:
            if bytes_per_sep > 0:
                if (n - i) % bytes_per_sep == 0:
                    out.append(sepc)
            else:
                if i % (0 - bytes_per_sep) == 0:
                    out.append(sepc)
        b = buf[i]
        out.append(ord(_HEX[b // 16]))
        out.append(ord(_HEX[b % 16]))
        i = i + 1
    return bytes(out)


def b2a_hex(data: bytes, sep: bytes = b"", bytes_per_sep: int = 1) -> bytes:
    return hexlify(data, sep, bytes_per_sep)


def unhexlify(hexstr) -> bytes:
    buf = _ascii_bytes(hexstr)
    n = len(buf)
    if n % 2 != 0:
        raise Error("Odd-length string")
    out = bytearray()
    i = 0
    while i < n:
        top = _hex_value(buf[i])
        bot = _hex_value(buf[i + 1])
        if top < 0 or bot < 0:
            raise Error("Non-hexadecimal digit found")
        out.append((top << 4) + bot)
        i = i + 2
    return bytes(out)


def a2b_hex(hexstr) -> bytes:
    return unhexlify(hexstr)


def b2a_base64(data: bytes, newline: bool = True) -> bytes:
    buf = _ascii_bytes(data)
    out = bytearray()
    n = len(buf)
    i = 0
    while i + 2 < n:
        v = (buf[i] << 16) | (buf[i + 1] << 8) | buf[i + 2]
        out.append(ord(_B64[v >> 18]))
        out.append(ord(_B64[(v >> 12) & 63]))
        out.append(ord(_B64[(v >> 6) & 63]))
        out.append(ord(_B64[v & 63]))
        i = i + 3
    left = n - i
    if left == 1:
        v = buf[i] << 16
        out.append(ord(_B64[v >> 18]))
        out.append(ord(_B64[(v >> 12) & 63]))
        out.append(61)
        out.append(61)
    elif left == 2:
        v = (buf[i] << 16) | (buf[i + 1] << 8)
        out.append(ord(_B64[v >> 18]))
        out.append(ord(_B64[(v >> 12) & 63]))
        out.append(ord(_B64[(v >> 6) & 63]))
        out.append(61)
    if newline:
        out.append(10)
    return bytes(out)


def a2b_base64(data, strict_mode: bool = False) -> bytes:
    buf = _ascii_bytes(data)
    n = len(buf)
    out = bytearray()
    if strict_mode and n > 0 and buf[0] == 61:
        raise Error("Leading padding not allowed")
    quad_pos = 0
    leftchar = 0
    pads = 0
    padding_started = 0
    done = 0
    i = 0
    while i < n:
        this = buf[i]
        if this == 61:
            padding_started = 1
            if quad_pos >= 2:
                pads = pads + 1
                if quad_pos + pads >= 4:
                    if strict_mode and i + 1 < n:
                        raise Error("Excess data after padding")
                    done = 1
                    break
            i = i + 1
            continue
        v = _b64_value(this)
        if v < 0:
            if strict_mode:
                raise Error("Only base64 data is allowed")
            i = i + 1
            continue
        if strict_mode and padding_started:
            raise Error("Discontinuous padding not allowed")
        pads = 0
        if quad_pos == 0:
            quad_pos = 1
            leftchar = v
        elif quad_pos == 1:
            quad_pos = 2
            out.append((leftchar << 2) | (v >> 4))
            leftchar = v & 15
        elif quad_pos == 2:
            quad_pos = 3
            out.append((leftchar << 4) | (v >> 2))
            leftchar = v & 3
        else:
            quad_pos = 0
            out.append((leftchar << 6) | v)
            leftchar = 0
        i = i + 1
    if not done and quad_pos != 0:
        if quad_pos == 1:
            raise Error("Invalid base64-encoded string: number of data characters (%d) cannot be 1 more than a multiple of 4" % (len(out) // 3 * 4 + 1))
        raise Error("Incorrect padding")
    return bytes(out)


def crc32(data: bytes, value: int = 0) -> int:
    buf = _ascii_bytes(data)
    crc = (value & 0xFFFFFFFF) ^ 0xFFFFFFFF
    i = 0
    while i < len(buf):
        crc = _CRC32_TABLE[(crc ^ buf[i]) & 0xFF] ^ (crc >> 8)
        i = i + 1
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def crc_hqx(data: bytes, value: int) -> int:
    buf = _ascii_bytes(data)
    crc = value & 0xFFFF
    i = 0
    while i < len(buf):
        crc = crc ^ (buf[i] << 8)
        k = 0
        while k < 8:
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
            k = k + 1
        i = i + 1
    return crc
