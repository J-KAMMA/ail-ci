import sys


def main() -> None:
    stack: list[str] = []
    out: list[str] = []
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        if cmd == "push":
            value = parts[1] if len(parts) > 1 else ""
            stack.append(value)
        elif cmd == "pop":
            if stack:
                out.append(stack.pop())
            else:
                out.append("empty")
        elif cmd == "peek":
            if stack:
                out.append(stack[-1])
            else:
                out.append("empty")
        elif cmd == "size":
            out.append(str(len(stack)))
    if out:
        sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
