from collections import Counter, OrderedDict, defaultdict, deque


def parse(line: str) -> tuple[str, str, int]:
    parts = line.split()
    return parts[0], parts[1], int(parts[2])


def main() -> int:
    lines = [
        "GET /index 200",
        "POST /login 200",
        "GET /index 500",
        "GET /about 200",
        "POST /login 403",
        "GET /index 200",
    ]
    status: Counter[int] = Counter()
    by_route: defaultdict[str, list[int]] = defaultdict(list)
    recent: deque[str] = deque(maxlen=3)
    order: OrderedDict[str, int] = OrderedDict()
    for line in lines:
        method, route, code = parse(line)
        status[code] += 1
        by_route[method + " " + route].append(code)
        recent.append(route)
        order[route] = order.get(route, 0) + 1
    for code, count in sorted(status.items()):
        print("status", code, count)
    for route in sorted(by_route):
        codes = by_route[route]
        print("route", route, len(codes), sum(codes) // len(codes))
    print("recent", list(recent))
    order.move_to_end("/index")
    for route in order:
        print("order", route, order[route])
    print(order.popitem(last=False))
    bad = Counter()
    for code in status:
        if code >= 400:
            bad[code] = status[code]
    print("bad", bad, bad.total())
    errors: dict[int, str] = {403: "forbidden", 500: "server"}
    for code in sorted(bad):
        print(code, errors.get(code, "unknown"))
    empty: deque[str] = deque()
    print(len(empty), list(empty))
    return 0


main()
