import json


def ordered(pairs: list) -> dict:
    return {key: value for key, value in pairs}


def main() -> None:
    text = '{"b": 2.5, "a": 1, "c": [1, 2]}'
    data = json.loads(text, object_hook=lambda d: {k: d[k] for k in sorted(d)})
    print(json.dumps(data, sort_keys=True))
    nums = json.loads("[1, 2.55, 3]", parse_float=lambda s: round(float(s), 1))
    print(nums, json.dumps(nums))
    pairs = json.loads('{"x": 1, "y": 2}', object_pairs_hook=lambda p: p)
    print(pairs)
    ordered_doc = json.loads('{"b": 2, "a": 1}', object_pairs_hook=ordered)
    print(list(ordered_doc.keys()))


main()
