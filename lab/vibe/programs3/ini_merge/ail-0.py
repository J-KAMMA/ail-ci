import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8")
    sections = {}
    current = ""
    bad = 0

    for raw in data.split("\n"):
        line = raw
        if line.endswith("\r"):
            line = line[:-1]
        line = line.strip(" \t")

        if line == "":
            continue

        first = line[0]

        if first == "#" or first == ";":
            continue

        if first == "[":
            if line.endswith("]"):
                name = line[1:-1]
                current = name
                if name not in sections:
                    sections[name] = {}
            else:
                bad += 1
            continue

        eq = line.find("=")
        if eq < 0:
            bad += 1
            continue

        key = line[:eq].strip(" \t")
        value = line[eq + 1:].strip(" \t")

        if key == "" or " " in key or "\t" in key:
            bad += 1
            continue

        if current not in sections:
            sections[current] = {}
        sections[current][key] = value

    out = ["bad " + str(bad)]

    for name in sorted(sections):
        out.append("[" + name + "]")
        values = sections[name]
        for key in sorted(values):
            out.append(key + "=" + values[key])

    sys.stdout.write("\n".join(out) + "\n")


main()
