import sys

PATHS = ["/api/items", "/api/users", "/api/orders", "/health", "/login", "/search", "/api/items/42", "/static/app.js"]
METHODS = ["GET", "GET", "GET", "POST", "PUT", "DELETE"]
STATUSES = ["200", "200", "200", "201", "204", "301", "400", "404", "500", "503"]
state = [1]

def rnd() -> int:
    state[0] = (state[0] * 1664525 + 1013904223) % 4294967296
    return state[0]

def pick(n: int) -> int:
    return (rnd() >> 8) % n

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: gen_log.py SEED N", file=sys.stderr)
        return 2
    state[0] = int(sys.argv[1]) % 4294967296
    count = int(sys.argv[2])
    for index in range(count):
        method = METHODS[pick(len(METHODS))]
        path = PATHS[pick(len(PATHS))]
        status = STATUSES[pick(len(STATUSES))]
        size_text = str(pick(20000))
        millis = pick(500)
        seconds = (10 * 3600 + index) % 86400
        stamp = "2026-11-04T%02d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60, seconds % 60)
        if (index + 1) % 10000 == 0:
            size_text = "99999999999999999999"
        elif pick(50) == 0:
            if pick(2) == 0:
                print(stamp, method, path)
                continue
            size_text = "not-a-number"
        print(stamp, method, path, status, size_text, millis)
    return 0

if __name__ == "__main__":
    sys.exit(main())
