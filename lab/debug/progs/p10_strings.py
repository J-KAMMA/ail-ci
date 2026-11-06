def join_words(ws: list[str]) -> str:
    parts = []
    for w in ws:
        parts.append(w.upper())
    return "-".join(parts)


def main() -> None:
    words = ["ab", "cd", "ef"]
    d = {}
    for w in words:
        d[w] = len(w)
    print(join_words(words), len(d))


main()
