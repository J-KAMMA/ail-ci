import bisect

CUTOFFS = [60, 70, 80, 90]
GRADES = ["F", "D", "C", "B", "A"]


def grade(score):
    return GRADES[bisect.bisect_right(CUTOFFS, score)]


def main():
    scores = [95, 72, 88, 59, 60, 79, 80, 100, 0]
    counts = {}
    for score in scores:
        letter = grade(score)
        counts[letter] = counts.get(letter, 0) + 1
    print("grades", " ".join(f"{letter}:{counts.get(letter, 0)}" for letter in GRADES))
    for score in sorted(scores):
        print(score, grade(score))
    print("pass", bisect.bisect_left(CUTOFFS, 60))
    print("honors", bisect.bisect_left(CUTOFFS, 90), bisect.bisect_right(CUTOFFS, 90))


main()
