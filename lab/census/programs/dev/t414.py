import sys


def main() -> None:
    stack: list[str] = []
    for raw_line in sys.stdin:
        parts = raw_line.strip().split()
        if not parts:
            continue
        command = parts[0].lower()
        if command == "push" and len(parts) >= 2:
            stack.append(parts[1])
        elif command == "pop":
            if stack:
                stack.pop()
        elif command == "size":
            # Query only; does not modify the stack.
            continue
        elif command == "peek":
            # Query only; does not modify the stack.
            continue
    print(" ".join(stack))


if __name__ == "__main__":
    main()
