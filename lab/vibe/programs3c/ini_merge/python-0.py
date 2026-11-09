import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8")
    lines = data.split("\n")

    bad = 0
    sections = {}
    current = ""

    for raw in lines:
        if raw.endswith("\r"):
            raw = raw[:-1]
        line = raw.strip(" \t")

        if line == "":
            continue

        if line[0] in "#;":
            continue

        if line[0] == "[":
            if len(line) >= 2 and line[-1] == "]":
                current = line[1:-1]
                sections.setdefault(current, {})
            else:
                bad += 1
            continue

        if "=" not in line:
            bad += 1
            continue

        key, _, value = line.partition("=")
        key = key.strip(" \t")
        value = value.strip(" \t")

        if key == "" or " " in key or "\t" in key:
            bad += 1
            continue

        sections.setdefault(current, {})[key] = value

    out = []
    out.append("bad %d\n" % bad)
    for name in sorted(sections.keys()):
        out.append("[%s]\n" % name)
        keys = sections[name]
        for k in sorted(keys.keys()):
            out.append("%s=%s\n" % (k, keys[k]))

    sys.stdout.buffer.write("".join(out).encode("utf-8"))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
