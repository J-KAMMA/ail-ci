import sys

def main() -> None:
    lines = sys.stdin.read().split("\n")

    words: list[str] = []
    for line in lines:
        if line == "":
            continue
        for word in line.split(" "):
            if word != "":
                words.append(word)

    if not words:
        return

    by_chars = max(words, key=len)
    by_bytes = max(words, key=lambda w: len(w.encode("utf-8")))

    print(f"{by_chars} {len(by_chars)}")
    print(f"{by_bytes} {len(by_bytes.encode('utf-8'))}")

if __name__ == "__main__":
    main()
