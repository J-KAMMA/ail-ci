def total(s, parts, table):
    t = 0.0
    for ch in s:
        t += 0.5
    for p in parts:
        t += 0.25
    for k, v in table.items():
        t += v * 1.5
    return t


def via_item(xs):
    t = 0.0
    for ch in xs[0]:
        t += 0.75
    return t


def via_dict(d):
    t = 0.0
    for ch in d["text"]:
        t += 0.125
    return t


print(total("abc", "a b c".split(), {"a": 1.5, "b": 2.5}))
print(total("", [], {}))
print(via_item(["xyz"]))
print(via_dict({"text": "hello"}))
