"""Word frequencies of a generated text: the top twenty words."""
import sys

SMALL = "--small" in sys.argv
WORD_COUNT = 6_000 if SMALL else 3_000_000
VOCABULARY = [
    "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
    "python", "rust", "compiler", "algorithm", "list", "dict", "set", "tuple",
    "heap", "queue", "graph", "tree", "sort", "search", "value", "index",
    "small", "large", "fast", "slow", "open", "close", "read", "write",
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
]

seed = 13579


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


words = []
for _ in range(WORD_COUNT):
    words.append(VOCABULARY[rnd() % len(VOCABULARY)])
text = " ".join(words)

counts = {}
for word in text.split():
    counts[word] = counts.get(word, 0) + 1

ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
checksum = 0
for word, count in counts.items():
    checksum += len(word) * count

print("words", WORD_COUNT)
print("distinct", len(counts))
print("checksum", checksum)
for word, count in ranked[:20]:
    print(word, count)
