import sys


def main() -> None:
    store: dict[str, int] = {}
    history: list[dict[str, int]] = []

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        if cmd == "set":
            key, value = parts[1], int(parts[2])
            history.append(dict(store))
            store[key] = value
        elif cmd == "incr":
            key, value = parts[1], int(parts[2])
            history.append(dict(store))
            store[key] = value
        elif cmd == "del":
            key = parts[1]
            history.append(dict(store))
            store.pop(key, None)
        elif cmd == "get":
            key = parts[1]
            print(store[key] if key in store else "nil")
        elif cmd == "count":
            print(len(store))

    for key in sorted(store):
        print(key, store[key])


if __name__ == "__main__":
    main()
