import sys
from decimal import Decimal


def main() -> None:
    tokens: list[str] = sys.stdin.read().split()
    if not tokens:
        return

    n: int = int(tokens[0])
    records: list[tuple[str, str, str, str]] = []
    idx: int = 1
    for _ in range(n):
        name: str = tokens[idx]
        grade: str = tokens[idx + 1]
        age: str = tokens[idx + 2]
        score: str = tokens[idx + 3]
        idx += 4
        records.append((name, grade, age, score))

    grade_rank: dict[str, int] = {"A": 0, "B": 1, "C": 2}

    def sort_key(rec: tuple[str, str, str, str]) -> tuple[int, Decimal, str]:
        name, grade, _age, score = rec
        return (
            grade_rank.get(grade, len(grade_rank)),
            -Decimal(score),
            name,
        )

    records.sort(key=sort_key)

    out_lines: list[str] = [
        f"{name} {grade} {age} {score}" for name, grade, age, score in records
    ]
    if out_lines:
        sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
