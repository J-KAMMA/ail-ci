import string

TEXT = "The quick brown fox, jumps over the lazy dog! The dog sleeps; the fox runs."
STOP = {"the", "a", "an"}


def words(text):
    cleaned = []
    for ch in text:
        if ch in string.ascii_letters or ch in string.digits:
            cleaned.append(ch.lower())
        else:
            cleaned.append(" ")
    return "".join(cleaned).split()


def main():
    tokens = words(TEXT)
    counts = {}
    for word in tokens:
        if word not in STOP:
            counts[word] = counts.get(word, 0) + 1
    for word in sorted(counts):
        print(word, counts[word])
    print("tokens", len(tokens), "unique", len(counts))
    print("letters", len(string.ascii_letters), "digits", len(string.digits))
    print("punctuation sample", string.punctuation[:6])


main()
