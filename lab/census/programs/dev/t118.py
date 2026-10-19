from typing import List


def interleave(a: str, b: str) -> str:
    result: List[str] = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            result.append(a[i])
        if i < len(b):
            result.append(b[i])
    return "".join(result)


def shared_sorted(a: str, b: str) -> str:
    return "".join(sorted(set(a) & set(b)))


def main() -> None:
    line = input().strip()
    parts = line.split()
    first = parts[0] if len(parts) > 0 else ""
    second = parts[1] if len(parts) > 1 else ""
    print(interleave(first, second))
    print(shared_sorted(first, second))


if __name__ == "__main__":
    main()
