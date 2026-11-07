def sizes(records: list[dict[str, str]]) -> list[int]:
    out = []
    for r in records:
        out.append(len(r))
    return out

print(sizes([{"a": "1"}, {"b": "2", "c": "3"}]))
