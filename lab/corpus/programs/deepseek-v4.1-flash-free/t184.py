import json
import sys


def flatten(value: object, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            flatten(child, f"{path}.{key}" if path else key, out)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            flatten(child, f"{path}[{index}]", out)
    else:
        line = f"{path} = {json.dumps(value)}" if path else json.dumps(value)
        out.append(line)


def main() -> None:
    data = json.loads(sys.stdin.readline())
    lines: list[str] = []
    flatten(data, "", lines)
    sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))


if __name__ == "__main__":
    main()
