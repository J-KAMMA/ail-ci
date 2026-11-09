import re
import sys

MAX = b"9223372036854775807"

PATTERN = re.compile(
    rb"([0-9]+)\.([0-9]+)\.([0-9]+)"
    rb"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    rb"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def numeric_ok(s: bytes) -> bool:
    t = s.lstrip(b"0")
    if not t:
        return True
    if len(t) > 19:
        return False
    return len(t) < 19 or t <= MAX


def numeric_value(s: bytes) -> int:
    t = s.lstrip(b"0")
    return int(t) if t else 0


def parse(line: bytes):
    m = PATTERN.fullmatch(line)
    if m is None:
        return None

    major_s, minor_s, patch_s, pre_s, build_s = m.groups()

    if not (numeric_ok(major_s) and numeric_ok(minor_s) and numeric_ok(patch_s)):
        return None

    if pre_s is not None:
        identifiers = pre_s.split(b".")
        for ident in identifiers:
            if ident.isdigit() and not numeric_ok(ident):
                return None

        pre_key = []
        for ident in identifiers:
            if ident.isdigit():
                pre_key.append((0, numeric_value(ident)))
            else:
                pre_key.append((1, ident))

        pre_key = tuple(pre_key)
        has_prerelease = 0
    else:
        pre_key = ()
        has_prerelease = 1

    if build_s is not None:
        for ident in build_s.split(b"."):
            if ident.isdigit() and not numeric_ok(ident):
                return None

    return (
        numeric_value(major_s),
        numeric_value(minor_s),
        numeric_value(patch_s),
        has_prerelease,
        pre_key,
        line,
    )


def main() -> None:
    data = sys.stdin.buffer.read()

    bad = 0
    accepted = []

    for line in data.split(b"\n"):
        if line.endswith(b"\r"):
            line = line[:-1]

        if line == b"":
            continue

        key = parse(line)
        if key is None:
            bad += 1
        else:
            accepted.append((key, line))

    accepted.sort(key=lambda item: item[0])

    output = [b"bad %d sorted %d\n" % (bad, len(accepted))]
    for _, line in accepted:
        output.append(line)
        output.append(b"\n")

    sys.stdout.buffer.write(b"".join(output))


if __name__ == "__main__":
    main()
