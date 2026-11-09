import sys


def main():
    text = sys.stdin.buffer.read().decode("utf-8")

    sections = {}
    current = ""
    bad = 0

    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        line = line.strip(" \t")

        if not line:
            continue

        if line[0] == "#" or line[0] == ";":
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

        if not key or " " in key or "\t" in key:
            bad += 1
            continue

        sections.setdefault(current, {})[key] = value

    output = [f"bad {bad}"]

    for name in sorted(sections):
        output.append(f"[{name}]")
        for key in sorted(sections[name]):
            output.append(f"{key}={sections[name][key]}")

    sys.stdout.buffer.write(("\n".join(output) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
