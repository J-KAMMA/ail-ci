import json

RECORDS = [
    {"id": 1, "name": "alpha", "active": True},
    {"id": 2, "name": "béta", "active": False},
]


def main() -> None:
    with open("records.json", "w", encoding="utf-8") as out:
        json.dump(RECORDS, out, indent=2, ensure_ascii=False, sort_keys=True)
        out.write("\n")
    with open("records.json", "r", encoding="utf-8") as src:
        loaded = json.load(src)
    print(len(loaded), loaded[1]["name"])
    print(json.dumps(loaded, sort_keys=True))
    print(json.dumps(loaded[0], separators=(",", ":")))


main()
