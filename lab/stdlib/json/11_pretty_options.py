import json


def main() -> None:
    data = {"b": [1, 2, {"c": "d"}], "a": [], "n": None, "ok": True}
    print(json.dumps(data))
    print(json.dumps(data, indent=2, sort_keys=True))
    print(json.dumps(data, indent=0, sort_keys=True))
    print(json.dumps(data, indent="\t"))
    print(json.dumps(data, separators=(",", ":")))
    print(json.dumps(data, separators=(" ,", " = "), indent=1))
    print(json.dumps([[], {}, [1], [1, [2]]], indent=1))
    print(json.dumps("é", ensure_ascii=False), json.dumps("é"))
    print(json.dumps({"z": 1, "a": 2}, sort_keys=True, ensure_ascii=False))


main()
