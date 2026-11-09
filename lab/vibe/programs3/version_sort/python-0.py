#!/usr/bin/env python3
import re
import sys

MAX_STR = b"9223372036854775807"

LINE_RE = re.compile(
    rb"([0-9]+)\.([0-9]+)\.([0-9]+)"
    rb"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    rb"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def parse_bounded(digits: bytes):
    stripped = digits.lstrip(b"0")
    if not stripped:
        return 0
    if len(stripped) > len(MAX_STR):
        return None
    if len(stripped) == len(MAX_STR) and stripped > MAX_STR:
        return None
    return int(stripped)


def prerelease_key(value: bytes):
    key = []
    for ident in value.split(b"."):
        if ident.isdigit():
            number = parse_bounded(ident)
            if number is None:
                return None
            key.append((0, number))
        else:
            key.append((1, ident))
    return tuple(key)


def valid_build(value: bytes):
    for ident in value.split(b"."):
        if ident.isdigit() and parse_bounded(ident) is None:
            return False
    return True


def main():
    data = sys.stdin.buffer.read()
    accepted = []
    bad = 0

    for raw_line in data.split(b"\n"):
        line = raw_line[:-1] if raw_line.endswith(b"\r") else raw_line
        if not line:
            continue

        match = LINE_RE.fullmatch(line)
        if match is None:
            bad += 1
            continue

        major = parse_bounded(match.group(1))
        minor = parse_bounded(match.group(2))
        patch = parse_bounded(match.group(3))
        if major is None or minor is None or patch is None:
            bad += 1
            continue

        prerelease = match.group(4)
        build = match.group(5)

        if build is not None and not valid_build(build):
            bad += 1
            continue

        if prerelease is None:
            no_prerelease = 1
            pre_key = ()
        else:
            pre_key = prerelease_key(prerelease)
            if pre_key is None:
                bad += 1
                continue
            no_prerelease = 0

        accepted.append(
            (major, minor, patch, no_prerelease, pre_key, line)
        )

    accepted.sort()

    output = bytearray()
    output.extend(f"bad {bad} sorted {len(accepted)}\n".encode())
    for item in accepted:
        output.extend(item[5])
        output.extend(b"\n")

    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
