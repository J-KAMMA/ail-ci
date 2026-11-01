import heapq


def main():
    scores = [
        ("alice", 90),
        ("bob", 75),
        ("carol", 90),
        ("dave", 88),
        ("eve", 60),
        ("frank", 88),
    ]
    print("top3", heapq.nlargest(3, scores, key=lambda row: row[1]))
    print("low3", heapq.nsmallest(3, scores, key=lambda row: row[1]))
    print("none", heapq.nlargest(0, scores))
    print("negative", heapq.nsmallest(-2, scores))
    numbers = [5, 1, 5, 3, 1, 3]
    print("dups", heapq.nlargest(4, numbers), heapq.nsmallest(4, numbers))
    print("over", heapq.nlargest(20, numbers))
    words = ["pear", "fig", "apple", "kiwi"]
    print("short", heapq.nsmallest(2, words, key=len))
    print("long", heapq.nlargest(2, words, key=len))
    print("plain", heapq.nlargest(2, words))


main()
