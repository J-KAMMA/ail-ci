import sys


def main() -> None:
    stack: list[str] = []
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        if cmd == "push":
            stack.append(parts[1])
        elif cmd == "pop":
            if stack:
                stack.pop()
        elif cmd == "peek":
            if stack:
                print(stack[-1])
        elif cmd == "size":
            print(len(stack))
    print(" ".join(stack))


if __name__ == "__main__":
    main()
