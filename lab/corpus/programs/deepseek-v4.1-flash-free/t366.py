import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    students = []
    for _ in range(n):
        name = next(it)
        grade = next(it)
        age = next(it)
        score = int(next(it))
        students.append((name, grade, age, score))

    students.sort(key=lambda s: (-s[3], s[0]))

    lines = []
    rank = 0
    prev_score = None
    for i, (name, grade, age, score) in enumerate(students):
        if score != prev_score:
            rank = i + 1
            prev_score = score
        lines.append(f"{rank} {name} {grade} {age} {score}")

    sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))


if __name__ == "__main__":
    main()
