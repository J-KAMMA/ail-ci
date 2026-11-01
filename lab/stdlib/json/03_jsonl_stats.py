import json

LINES = [
    '{"level": "info", "ms": 12, "msg": "start"}',
    '{"level": "warn", "ms": 30, "msg": "slow"}',
    '{"level": "info", "ms": 7}',
    '{"level": "error", "ms": 5, "msg": "boom"}',
    'not json at all',
    '{"level": "warn", "ms": 3}',
]


def main() -> None:
    counts = {}
    total = 0
    for line in LINES:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            print("skip:", line)
            continue
        level = record["level"]
        counts[level] = counts.get(level, 0) + 1
        total += record.get("ms", 0)
    print(json.dumps(counts, sort_keys=True))
    print(json.dumps({"events": len(LINES), "total_ms": total}))


main()
