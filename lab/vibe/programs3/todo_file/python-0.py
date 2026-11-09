import sys

MAX_ID = 2147483647


def parse_id(token):
    if not token:
        return None
    for ch in token:
        if ch < "0" or ch > "9":
            return None

    stripped = token.lstrip("0")
    if not stripped or len(stripped) > 10:
        return None

    value = int(stripped)
    if value > MAX_ID:
        return None
    return value


def main():
    if len(sys.argv) < 2:
        return

    items = {}
    errors = 0
    output = []

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        for raw_line in f:
            if raw_line.endswith("\n"):
                line = raw_line[:-1]
            else:
                line = raw_line

            if line == "":
                continue

            first_space = line.find(" ")
            if first_space == -1:
                command = line
                rest = None
            else:
                command = line[:first_space]
                rest = line[first_space + 1:]

            if command == "add":
                item_id = None
                text = None

                if rest is not None:
                    second_space = rest.find(" ")
                    if second_space != -1:
                        id_token = rest[:second_space]
                        text = rest[second_space + 1:]
                        if text != "":
                            item_id = parse_id(id_token)

                if item_id is None or item_id in items:
                    errors += 1
                    output.append("error add")
                else:
                    items[item_id] = [False, text]
                    output.append(f"added {item_id}")

            elif command in ("done", "remove", "show"):
                item_id = None
                if rest is not None and " " not in rest:
                    item_id = parse_id(rest)

                if item_id is None:
                    errors += 1
                    output.append(f"error {command}")
                elif command == "done":
                    item = items.get(item_id)
                    if item is None or item[0]:
                        errors += 1
                        output.append("error done")
                    else:
                        item[0] = True
                        output.append(f"done {item_id}")
                elif command == "remove":
                    if item_id not in items:
                        errors += 1
                        output.append("error remove")
                    else:
                        del items[item_id]
                        output.append(f"removed {item_id}")
                else:
                    item = items.get(item_id)
                    if item is None:
                        errors += 1
                        output.append("error show")
                    else:
                        state = "done" if item[0] else "open"
                        output.append(f"todo {item_id} {state} {item[1]}")

            elif command in ("list", "stats"):
                if rest is not None:
                    errors += 1
                    output.append(f"error {command}")
                elif command == "list":
                    open_ids = sorted(
                        item_id
                        for item_id, item in items.items()
                        if not item[0]
                    )
                    output.append(f"list {len(open_ids)}")
                    for item_id in open_ids:
                        output.append(f"todo {item_id} open {items[item_id][1]}")
                else:
                    total = len(items)
                    opened = sum(1 for item in items.values() if not item[0])
                    done = total - opened
                    chars = sum(len(item[1]) for item in items.values())
                    output.append(
                        f"stats total {total} open {opened} done {done} "
                        f"chars {chars} errors {errors}"
                    )

            else:
                errors += 1
                if command == "":
                    output.append("error error")
                else:
                    output.append(f"error {command}")

    if output:
        sys.stdout.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
