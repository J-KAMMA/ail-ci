# task: Write a Playable base class with a play method and Game subclasses that each track score differently, printing final scores after fixed rounds.
from __future__ import annotations

import random
from abc import ABC, abstractmethod


class Playable(ABC):
    """Base class for anything that can be played for a fixed number of rounds."""

    def __init__(self, name: str, rounds: int) -> None:
        self.name = name
        self.rounds = rounds
        self.score: int = 0

    @abstractmethod
    def play(self, round_number: int) -> None:
        """Play a single round, updating the score."""

    def run(self) -> int:
        """Play all rounds and return the final score."""
        for round_number in range(1, self.rounds + 1):
            self.play(round_number)
        return self.score


class DiceGame(Playable):
    """Scores the sum of two dice each round."""

    def __init__(self, rounds: int, rng: random.Random) -> None:
        super().__init__("Dice Game", rounds)
        self.rng = rng

    def play(self, round_number: int) -> None:
        roll = self.rng.randint(1, 6) + self.rng.randint(1, 6)
        self.score += roll


class HighLowGame(Playable):
    """Gains a point for each correct guess of higher or lower, loses one otherwise."""

    def __init__(self, rounds: int, rng: random.Random) -> None:
        super().__init__("High-Low Game", rounds)
        self.rng = rng
        self.previous: int = self.rng.randint(1, 13)

    def play(self, round_number: int) -> None:
        current = self.rng.randint(1, 13)
        guess_higher = round_number % 2 == 0  # deterministic guessing pattern
        if current == self.previous:
            pass  # ties score nothing
        elif (current > self.previous) == guess_higher:
            self.score += 1
        else:
            self.score -= 1
        self.previous = current


class StreakGame(Playable):
    """Score grows with consecutive wins; a loss resets the streak."""

    def __init__(self, rounds: int, rng: random.Random) -> None:
        super().__init__("Streak Game", rounds)
        self.rng = rng
        self.streak: int = 0

    def play(self, round_number: int) -> None:
        won = self.rng.random() < 0.6
        if won:
            self.streak += 1
            self.score += self.streak
        else:
            self.streak = 0


def main() -> None:
    random.seed(2024)
    rng = random.Random(2024)
    rounds = 10

    games: list[Playable] = [
        DiceGame(rounds, rng),
        HighLowGame(rounds, rng),
        StreakGame(rounds, rng),
    ]

    for game in games:
        final = game.run()
        print(f"{game.name} final score after {game.rounds} rounds: {final}")


if __name__ == "__main__":
    main()
