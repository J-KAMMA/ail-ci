def repeat(s: str, n: int) -> str:
    out = ""
    for _ in range(n):
        out = out + s
    return out


def main() -> None:
    word = repeat("ab", 3)
    print(word)
    print(word.upper())
    print(word.startswith("ab"))
    print(len(word), word[1], word[-1])
    words = []
    for piece in word.split("b"):
        words.append(piece)
    print(len(words), ",".join(words))


main()
