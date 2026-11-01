from enum import IntEnum


class Level(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


def enabled(level, threshold):
    return level >= threshold


def main():
    events = [
        (Level.DEBUG, "cache"),
        (Level.ERROR, "disk"),
        (Level.INFO, "start"),
        (Level.WARNING, "slow"),
        (Level.CRITICAL, "crash"),
    ]
    threshold = Level.WARNING
    shown = []
    for level, message in events:
        if enabled(level, threshold):
            shown.append(message.upper())
    print(shown)

    counts = {}
    for level, _ in events:
        counts[level] = counts.get(level, 0) + 1
    for level in Level:
        if level in counts:
            print(level.name, level.value, counts[level])

    print([lvl.name for lvl in Level if lvl >= threshold])
    print(max(Level), min(Level), sum(lvl.value for lvl in Level))
    print(Level(30), Level["INFO"], str(Level.ERROR), repr(Level.DEBUG))
    try:
        Level["TRACE"]
    except KeyError as error:
        print("unknown", error)


main()
