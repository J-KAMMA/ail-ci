import re

FIELD = re.compile(r'"([^"]*)"|([^,]+)')


def parse(line: str) -> list[str]:
    out = []
    for m in FIELD.finditer(line):
        if m.group(1) is not None:
            out.append(m.group(1))
        else:
            out.append(m.group(2).strip())
    return out


def main() -> int:
    for line in ['a,b,c', '"x,y",z', '', ' "q" , r ']:
        fields = parse(line)
        print(len(fields), fields)
    print(re.split(r",", "a,b,,c"))
    print(re.split(r"(\s*,\s*)", "a , b,c"))
    print(re.split(r"\s+", "  a  b  "))
    return 0


main()
