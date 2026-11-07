"""Lexer: turn source text into tokens by scanning character by character."""


def is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def count_idents(src: str) -> int:
    n = 0
    i = 0
    size = len(src)
    while i < size:
        ch = src[i]
        if is_ident_start(ch):
            j = i + 1
            while j < size and is_ident_char(src[j]):
                j += 1
            n += 1
            i = j
        else:
            i += 1
    return n


def longest_ident(src: str) -> int:
    best = 0
    i = 0
    size = len(src)
    while i < size:
        if is_ident_start(src[i]):
            j = i + 1
            while j < size and is_ident_char(src[j]):
                j += 1
            run = j - i
            if run > best:
                best = run
            i = j
        else:
            i += 1
    return best


def count_keywords(src: str, kw: str) -> int:
    hits = 0
    i = 0
    size = len(src)
    target = len(kw)
    while i + target <= size:
        if src[i] == kw[0]:
            match = 1
            j = 1
            while j < target and src[i + j] == kw[j]:
                match += 1
                j += 1
            if match == target:
                hits += 1
                i += target
                continue
        i += 1
    return hits


def digit_count(src: str) -> int:
    n = 0
    for ch in src:
        if ch.isdigit():
            n += 1
    return n


def token_weight(src: str) -> int:
    total = 0
    for ch in src:
        if ch.isalpha():
            total += 2
        elif ch.isdigit():
            total += 3
        elif ch.isspace():
            total += 1
    return total
