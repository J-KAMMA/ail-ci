def add_one(x: int) -> int:
    return x + 1


def half(x: float) -> float:
    return x / 2.0


def probe() -> None:
    a = 1 / 2
    b = not 1
    c = abs(-3.5)
    d = sum([1.5, 2.5])
    n = round(1.234, 2)
    i = 2 + 3
    j = 7 // 2
    k = 7 % 3
    p = 2 ** 3
    q = -5
    r = 3 * 4
    s = 1.5 + 2.5
    t = 2.0 * 3.0
    u = add_one(4)
    v = half(5.0)
    w = len("abcd")
    total = 0
    total = total + i
    for idx in range(3):
        total = total + idx
    nums = [1, 2, 3]
    first = nums[0]
    floats = [1.5, 2.5]
    second = floats[1]
    words = ["a", "b"]
    word = words[0]
    mapping = {1: 2, 3: 4}
    value = mapping[1]
    text = "hello"
    upper = text.upper()
    pieces = text.split()
    stripped = text.strip()
    replaced = text.replace("l", "L")
    count = text.count("l")
    ratio = i / 2
    mutated_list = [True, False]
    mutated_list[0] = 1
    mutated_item = mutated_list[0]
    mutated_dict = {"a": True}
    mutated_dict["a"] = 1
    mutated_dict_item = mutated_dict["a"]
    appended_list = [True, False]
    appended_list.append(1)
    appended_item = appended_list[2]
    mixed = 1
    mixed = 2.5
    print(a, b, c, n, i, j, k, p, q, r, s, t, u, v, w, total, idx, first,
          second, word, value, text, upper, pieces, stripped, replaced,
          count, ratio, mutated_item, mutated_dict_item, appended_item, mixed)


def main() -> None:
    probe()


main()
