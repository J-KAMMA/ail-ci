import fnmatch


def main():
    logs = [
        "service.log",
        "service.log.1",
        "service.log.2",
        "service.log.10",
        "service.log.gz",
        "worker.log",
        "worker.log.1",
        "worker.out",
        "old-service.log.7",
        "service.log.2026-10-31",
    ]
    print("numbered:", fnmatch.filter(logs, "*.log.[0-9]"))
    print("rotated:", fnmatch.filter(logs, "*.log.*"))
    print("compressed:", fnmatch.filter(logs, "*.gz"))
    print("worker:", fnmatch.filter(logs, "worker.*"))
    print("old:", fnmatch.filter(logs, "old-*.log.*"))
    for name in logs:
        digits = fnmatch.fnmatchcase(name, "service.log.[0-9]*")
        either = fnmatch.fnmatchcase(name, "service.log") or fnmatch.fnmatchcase(name, "service.log.*")
        print(name, digits, either)
    print("none:", fnmatch.filter(logs, "*.log.[!0-9]"))


main()
