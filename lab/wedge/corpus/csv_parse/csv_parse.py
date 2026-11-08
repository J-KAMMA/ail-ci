"""CSV-like parser: split rows on commas and fields on quotes."""

COMMA = ","


def split_lines(text: str) -> list[str]:
    out = []
    cur = ""
    for ch in text:
        if ch == "\n":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur != "":
        out.append(cur)
    return out


def count_fields(line: str) -> int:
    n = 1
    in_quote = 0
    for ch in line:
        if ch == '"':
            in_quote = 1 - in_quote
        elif ch == COMMA and in_quote == 0:
            n += 1
    return n


def field_chars(line: str) -> int:
    n = 0
    in_quote = 0
    for ch in line:
        if ch == '"':
            in_quote = 1 - in_quote
        elif ch == COMMA:
            pass
        else:
            n += 1
    return n


def sum_column(text: str, col: int) -> int:
    total = 0
    count = 0
    body = ""
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\n":
            if body != "":
                total += int(body)
            body = ""
            count = 0
        elif ch == COMMA:
            if count == col and body != "":
                total += int(body)
            count += 1
            body = ""
        elif count == col:
            body += ch
        i += 1
    if body != "":
        total += int(body)
    return total


def max_field_len(text: str) -> int:
    best = 0
    cur = 0
    for ch in text:
        if ch == COMMA or ch == "\n":
            if cur > best:
                best = cur
            cur = 0
        else:
            cur += 1
    if cur > best:
        best = cur
    return best


def quote_count(text: str) -> int:
    n = 0
    for ch in text:
        if ch == '"':
            n += 1
    return n
