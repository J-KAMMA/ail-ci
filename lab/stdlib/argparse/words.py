import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Count words from standard input.")
    parser.add_argument("files", nargs="*", help="labels for the input")
    parser.add_argument("--top", type=int, default=3, metavar="N")
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--separator", default=" ")
    args = parser.parse_args()
    words = sys.stdin.read().split()
    if args.ignore_case:
        words = [word.lower() for word in words]
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    ordered = sorted(counts, key=lambda word: (-counts[word], word))
    for word in ordered[:args.top]:
        print(f"{word}{args.separator}{counts[word]}")
    print("files", len(args.files), args.files)


if __name__ == "__main__":
    main()
