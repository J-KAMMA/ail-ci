# task: Use enum.auto() to define a set of command types and use a match statement to print a description for each command in a fixed list.
from __future__ import annotations

from enum import Enum, auto


class CommandType(Enum):
    START = auto()
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    STATUS = auto()
    RESET = auto()


COMMANDS: list[CommandType] = [
    CommandType.START,
    CommandType.STATUS,
    CommandType.PAUSE,
    CommandType.RESUME,
    CommandType.STOP,
    CommandType.RESET,
    CommandType.STATUS,
]


def describe(command: CommandType) -> str:
    match command:
        case CommandType.START:
            return "Start the system and begin processing tasks."
        case CommandType.STOP:
            return "Stop the system and release all resources."
        case CommandType.PAUSE:
            return "Temporarily suspend processing without losing state."
        case CommandType.RESUME:
            return "Continue processing from the last paused state."
        case CommandType.STATUS:
            return "Report the current state of the system."
        case CommandType.RESET:
            return "Return the system to its initial configuration."
        case _:
            return "Unknown command."


def main() -> None:
    for index, command in enumerate(COMMANDS, start=1):
        print(f"{index}. {command.name} (value={command.value}): {describe(command)}")


if __name__ == "__main__":
    main()
