import re

DATE = re.compile(r"(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})")


def main() -> int:
    text = "due 2026-10-17, later 2026/11/1 and 2026-1-2"
    print(DATE.sub(r"\g<d>.\g<m>.\g<y>", text))
    print(DATE.sub(r"\3/\2/\1", text, count=1))
    for m in DATE.finditer(text):
        print(m.group("y"), int(m.group("m")), int(m.group("d")), m.start(), m.end())
    print(DATE.findall(text))
    print(DATE.sub(lambda m: m.group("y") + "-" + m.group("m").zfill(2) + "-" + m.group("d").zfill(2), text))
    for part in re.split(r"[,;]\s*", "a, b; c"):
        print(part)
    print(DATE.search("no date") is None)
    return 0


main()
