import json
import sys
from typing import Any


def main() -> None:
    raw: str = sys.stdin.read()
    if not raw.strip():
        return

    records: list[dict[str, Any]] = json.loads(raw)

    # Stable sort: equal scores keep their original input order.
    ranked: list[dict[str, Any]] = sorted(
        records,
        key=lambda rec: rec["score"],
        reverse=True,
    )

    for rec in ranked[:2]:
        print(json.dumps(rec, sort_keys=True))


if __name__ == "__main__":
    main()
