"""Hashing and checksums over bytes-like integer data."""


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for byte in data:
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def fnv1a_64(data: bytes) -> int:
    h = 1469598103934665603
    for byte in data:
        h ^= byte
        h = (h * 1099511628211) & 0x7FFFFFFFFFFFFFFF
    return h


def crc32_table_free(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        k = 0
        while k < 8:
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc = crc >> 1
            k += 1
    return crc ^ 0xFFFFFFFF


def adler32_simple(data: bytes) -> int:
    a = 1
    b = 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def djb2(text: str) -> int:
    h = 5381
    for ch in text:
        h = ((h * 33) + ord(ch)) & 0x7FFFFFFF
    return h


def sum_bytes(data: bytes) -> int:
    total = 0
    for byte in data:
        total += byte
    return total


def xor_fold(data: bytes) -> int:
    acc = 0
    for byte in data:
        acc ^= byte
    return acc
