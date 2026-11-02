from collections import defaultdict


def key_of(word: str) -> str:
    letters = []
    for ch in word:
        letters.append(ch)
    letters.sort()
    return "".join(letters)


def main() -> int:
    words = ["eat", "tea", "tan", "ate", "nat", "bat", "tab", "cat"]
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for word in words:
        groups[key_of(word)].append(word)
    for key in sorted(groups):
        row = groups[key]
        row.sort()
        print(key, len(row), ",".join(row))
    print(len(groups), groups["xyz"])
    print(len(groups), "xyz" in groups)
    missing = groups.get("nope", [])
    print(missing, len(groups))
    groups["miss"].append("sim")
    groups["miss"].extend(["ism", "mis"])
    print(groups["miss"])
    total = 0
    for key in groups:
        total += len(groups[key])
    print(total)
    empty: defaultdict[str, list[str]] = defaultdict(list)
    for word in empty["fresh"]:
        print("never")
    print(len(empty), empty["fresh"])
    return 0


main()
