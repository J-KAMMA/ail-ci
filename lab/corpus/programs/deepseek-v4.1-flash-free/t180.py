import json
import sys


def main() -> None:
    data = sys.stdin.read().strip()
    if not data:
        return

    records = json.loads(data)

    lines: list[tuple[object, str]] = []
    for record in records:
        if "meta" not in record:
            continue
        meta = record["meta"]
        note = meta["note"] if meta["note"] is not None else "-"
        lines.append(
            (record["id"], f"{record['id']}: level={meta['level']} note={note}")
        )

    lines.sort(key=lambda item: item[0])
    for _, line in lines:
        sys.stdout.write(line + "\n")


if __name__ == "__main__":
    main()
