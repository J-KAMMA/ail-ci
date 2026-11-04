import keyword


def main() -> None:
    words = ["if", "else", "value", "_", "match", "", "def", "classy", "None", "true"]
    chosen = [w for w in words if keyword.iskeyword(w)]
    print("comp", chosen)
    filtered = list(filter(keyword.iskeyword, words))
    print("filter", filtered)
    print("same", len(chosen) == len(filtered) and chosen[0] == filtered[0] and chosen[-1] == filtered[-1])
    flags = [keyword.iskeyword(w) for w in words]
    print("flags", len(flags), flags[0], flags[4], flags[9])
    soft = list(filter(keyword.issoftkeyword, words))
    print("soft", soft)
    print("counts", len(chosen), len(filtered), len(soft))


main()
