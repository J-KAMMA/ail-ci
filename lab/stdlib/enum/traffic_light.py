from enum import Enum, auto


class Signal(Enum):
    RED = auto()
    YELLOW = auto()
    GREEN = auto()

    def next_signal(self):
        if self is Signal.RED:
            return Signal.GREEN
        if self is Signal.GREEN:
            return Signal.YELLOW
        return Signal.RED

    @property
    def stop(self):
        return self is Signal.RED


def main():
    light = Signal.RED
    for _ in range(4):
        state = "stop" if light.stop else "go"
        print(light.name, light.value, state)
        light = light.next_signal()
    print([s.name for s in Signal], len(Signal))
    print(Signal["YELLOW"], Signal(3))
    try:
        Signal(99)
    except ValueError as error:
        print("bad value:", error)
    try:
        Signal["BLUE"]
    except KeyError as error:
        print("bad name:", error)


main()
