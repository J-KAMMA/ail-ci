import keyword


def is_long(word: str) -> bool:
    return len(word) > 2


def keep_keywords(words: list[str]) -> list[str]:
    kept = []
    for word in words:
        if keyword.iskeyword(word):
            kept.append(word)
    return kept


def main() -> None:
    words = ["if", "else", "value", "_", "match", "", "def", "classy", "None", "true"]
    chosen = [w for w in words if keyword.iskeyword(w)]
    print("comp", chosen)
    filtered = keep_keywords(words)
    print("filter", filtered)
    print("same", len(chosen) == len(filtered) and chosen[0] == filtered[0] and chosen[-1] == filtered[-1])
    flags = [keyword.iskeyword(w) for w in words]
    print("flags", len(flags), flags[0], flags[4], flags[9])
    soft = [w for w in words if keyword.issoftkeyword(w)]
    print("soft", soft)
    print("long", list(filter(is_long, words)))
    print("counts", len(chosen), len(filtered), len(soft))


main()
