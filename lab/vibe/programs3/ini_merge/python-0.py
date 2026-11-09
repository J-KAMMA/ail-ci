import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8")

    sections = {}
    current = ""
    bad = 0

    for raw in data.split("\n"):
        if raw.endswith("\r"):
            raw = raw[:-1]

        line = raw.strip(" \t")

        if line == "":
            continue

        if line[0] in "#;":
            continue

        if line[0] == "[":
            if line.endswith("]"):
                current = line[1:-1]
                sections.setdefault(current, {})
            else:
                bad += 1
            continue

        if "=" not in line:
            bad += 1
            continue

        key, value = line.split("=", 1)
        key = key.strip(" \t")
        value = value.strip(" \t")

        if key == "" or " " in key or "\t" in key:
            bad += 1
            continue

        sections.setdefault(current, {})[key] = value

    output = [f"bad {bad}\n"]

    for name in sorted(sections):
        output.append(f"[{name}]\n")
        for key in sorted(sections[name]):
            output.append(f"{key}={sections[name][key]}\n")

    sys.stdout.write("".join(output))


if __name__ == "__main__":
    main()
