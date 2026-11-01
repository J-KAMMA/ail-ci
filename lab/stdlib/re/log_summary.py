import re

LOG = re.compile(r"(?P<level>[A-Z]+)\s+(?P<ts>\d{4}-\d{2}-\d{2})\s+(?P<msg>.+)")
COUNT = re.compile(r"error", re.I)


def main() -> int:
    lines = [
        "INFO 2026-10-01 started",
        "ERROR 2026-10-01 disk full",
        "WARN 2026-10-02 low memory",
        "not a log line",
        "ERROR 2026-10-03 write error again",
    ]
    errors = 0
    for line in lines:
        m = LOG.match(line)
        if m is None:
            print("skip", line)
            continue
        fields = m.groupdict()
        print(m.group("level"), m.group("ts"), len(m.group("msg")))
        if COUNT.search(fields["msg"]):
            errors += 1
    print("errors", errors)
    return 0


main()
