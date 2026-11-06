"""Generate the two texts used by lab/regex: a 20 MB log-like ASCII file and a 2 MB mixed
non-ASCII file.  Both are seeded, so every run produces the same bytes.

    python3 lab/regex/gen_text.py --out /tmp/ffre1-data
    python3 lab/regex/gen_text.py --out /tmp/ffre1-data --seed 7

The ASCII text is one log record per line:

    <ts> <host> <app>: level=<level> msg="user=<user> id=<id> ip=<ip> path=<path>
    status=<status> csv=<a>, <b>,<c> , <d>"

The message has exactly three commas, so `re.split(r"\\s*,\\s*", line)` always yields four
fields.  Levels are mixed case, IPv4 octets are mostly valid with a few deliberately out of
range, and every line is ASCII.  The mixed text is UTF-8 (Latin, Greek, Cyrillic, CJK and
Arabic-Indic digits) and contains the literal word "café" on every line.
"""
import argparse
import random
from pathlib import Path

ASCII_BYTES = 20 * 1024 * 1024
MIXED_BYTES = 2 * 1024 * 1024
LEVELS = ["INFO", "info", "WARN", "warn", "ERROR", "error", "FATAL", "fatal", "DEBUG", "TRACE"]
APPS = ["auth", "api", "worker", "db", "cache", "sched", "proxy", "mailer"]
PATHS = ["/a/b", "/api/v1/users", "/health", "/login", "/v2/orders", "/static/app.js", "/x/y/z"]
USERS = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi"]
WORDS = ["error", "warn", "fatal", "timeout", "retry", "connect", "flush", "ready", "slow",
         "batch", "queue", "cache", "miss", "hit", "route", "token", "login", "logout"]
MIXED_WORDS = ["café", "résumé", "naïve", "αβγ", "δεζ", "Москва", "данные", "東京", "日本",
               "データ", "٣٤", "٥٦", "ñandú", "über"]


def ipv4(rng, bad):
    if bad:
        return "%d.%d.%d.%d" % (rng.choice([256, 300, 999]), rng.randrange(10), 1, 2)
    return "%d.%d.%d.%d" % (rng.randrange(10, 224), rng.randrange(256),
                            rng.randrange(256), rng.randrange(1, 255))


def ascii_line(rng, n):
    ts = "2026-%02d-%02dT%02d:%02d:%02dZ" % (rng.randrange(1, 13), rng.randrange(1, 29),
                                             rng.randrange(24), rng.randrange(60),
                                             rng.randrange(60))
    host = "host%02d" % rng.randrange(1, 41)
    app = APPS[rng.randrange(len(APPS))]
    level = LEVELS[rng.randrange(len(LEVELS))]
    user = USERS[rng.randrange(len(USERS))]
    ident = rng.randrange(1, 1000000)
    ip = ipv4(rng, n % 997 == 0)
    path = PATHS[rng.randrange(len(PATHS))]
    status = rng.choice([200, 200, 200, 201, 204, 301, 400, 404, 500, 503])
    msg = WORDS[rng.randrange(len(WORDS))]
    a = "f%d" % rng.randrange(10000)
    b = "g%d" % rng.randrange(10000)
    c = "h%d" % rng.randrange(10000)
    d = "i%d" % rng.randrange(10000)
    return ('%s %s %s: level=%s msg="user=%s id=%d ip=%s path=%s status=%d %s '
            'csv=%s, %s,%s , %s"\n' % (ts, host, app, level, user, ident, ip, path,
                                       status, msg, a, b, c, d))


def mixed_line(rng):
    picks = [MIXED_WORDS[rng.randrange(len(MIXED_WORDS))] for _ in range(6)]
    return "café " + " ".join(picks) + " id=%d\n" % rng.randrange(1, 1000000)


def write_ascii(path, target, rng):
    total = 0
    n = 0
    with open(path, "w", encoding="ascii", newline="\n") as f:
        while total < target:
            chunk = []
            for _ in range(1000):
                line = ascii_line(rng, n)
                chunk.append(line)
                n += 1
            text = "".join(chunk)
            f.write(text)
            total += len(text)
    return total, n


def write_mixed(path, target, rng):
    total = 0
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        while total < target:
            chunk = []
            for _ in range(1000):
                line = mixed_line(rng)
                chunk.append(line)
                n += 1
            text = "".join(chunk)
            f.write(text)
            total += len(text.encode("utf-8"))
    return total, n


def generate(out_dir, seed=20261106):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    ascii_path = out / "ascii.txt"
    mixed_path = out / "mixed.txt"
    ascii_size, ascii_lines = write_ascii(ascii_path, ASCII_BYTES, rng)
    mixed_size, mixed_lines = write_mixed(mixed_path, MIXED_BYTES, rng)
    return {
        "ascii": str(ascii_path),
        "ascii_bytes": ascii_size,
        "ascii_lines": ascii_lines,
        "mixed": str(mixed_path),
        "mixed_bytes": mixed_size,
        "mixed_lines": mixed_lines,
        "seed": seed,
    }


def main():
    ap = argparse.ArgumentParser(description="generate the lab/regex texts")
    ap.add_argument("--out", default="/tmp/ffre1-data", help="output directory")
    ap.add_argument("--seed", type=int, default=20261106)
    args = ap.parse_args()
    info = generate(args.out, args.seed)
    print("ascii %(ascii_bytes)d bytes %(ascii_lines)d lines %(ascii)s" % info)
    print("mixed %(mixed_bytes)d bytes %(mixed_lines)d lines %(mixed)s" % info)


if __name__ == "__main__":
    main()
