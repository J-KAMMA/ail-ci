"""pydantic-like field checks: normalise a string and validate a record."""

MAX_NAME = 64
MIN_SCORE = 0
MAX_SCORE = 100


def normalise_name(raw: str) -> str:
    out = ""
    last_space = True
    for ch in raw:
        if ch == " " or ch == "\t":
            if not last_space:
                out += " "
            last_space = True
        else:
            out += ch
            last_space = False
    return out


def is_upper_name(name: str) -> bool:
    for ch in name:
        if ch >= "a" and ch <= "z":
            return False
    return True


def is_simple_email(addr: str) -> bool:
    at = 0
    dots = 0
    for ch in addr:
        if ch == "@":
            at += 1
        elif ch == ".":
            dots += 1
    return at == 1 and dots >= 1


def valid_len(name: str) -> bool:
    n = 0
    for _ch in name:
        n += 1
    return n > 0 and n <= MAX_NAME


def score_ok(score: int) -> bool:
    return score >= MIN_SCORE and score <= MAX_SCORE


def field_weight(name: str, score: int, email: str) -> int:
    w = 0
    for ch in name:
        w += 1
    w += score * 2
    for ch in email:
        if ch == "@":
            w += 5
    return w


def looks_like_version(tag: str) -> bool:
    dot = 0
    for ch in tag:
        if ch == ".":
            dot += 1
    return dot >= 2
