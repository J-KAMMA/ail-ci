import re

WORD = re.compile(r"[A-Za-z']+")


def main() -> int:
    text = "The cat sat on the mat. The CAT saw another cat!"
    counts = {}
    for word in WORD.findall(text):
        key = word.lower()
        counts[key] = counts.get(key, 0) + 1
    for word in sorted(counts):
        print(word, counts[word])
    print(len(WORD.findall("")), WORD.search("") is None)
    print(re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", "well-known") is not None)
    m = re.search(r"\bcat\b", "concatenate cat")
    if m:
        print(m.start(), m.end(), m.group(0))
    print(re.findall(r"\bth\w*", text))
    print(re.sub(r"[.!?]", "", text))
    return 0


main()
