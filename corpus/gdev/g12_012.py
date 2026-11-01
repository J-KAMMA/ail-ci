# task: Simulate a call center with five agents and seeded call arrivals, then print how many calls received a busy signal.
import random
from dataclasses import dataclass

NUM_AGENTS: int = 5
NUM_CALLS: int = 10_000
SEED: int = 2024
MEAN_INTERARRIVAL: float = 1.0   # average minutes between calls
MEAN_SERVICE: float = 4.0        # average minutes per call


@dataclass
class CallCenterStats:
    offered: int = 0
    answered: int = 0
    busy_signals: int = 0


def simulate(rng: random.Random) -> CallCenterStats:
    """Run the call center simulation and return summary statistics."""
    stats = CallCenterStats()
    # Time at which each agent becomes free again (0.0 means free now).
    agent_free_at: list[float] = [0.0] * NUM_AGENTS
    clock: float = 0.0

    for _ in range(NUM_CALLS):
        clock += rng.expovariate(1.0 / MEAN_INTERARRIVAL)
        stats.offered += 1

        # Find the first agent who is free at the arrival time.
        chosen: int | None = None
        for index, free_at in enumerate(agent_free_at):
            if free_at <= clock:
                chosen = index
                break

        if chosen is None:
            # Every agent is busy: the caller hears a busy signal.
            stats.busy_signals += 1
        else:
            service_time = rng.expovariate(1.0 / MEAN_SERVICE)
            agent_free_at[chosen] = clock + service_time
            stats.answered += 1

    return stats


def main() -> None:
    rng = random.Random(SEED)
    stats = simulate(rng)

    print(f"Agents: {NUM_AGENTS}")
    print(f"Calls offered: {stats.offered}")
    print(f"Calls answered: {stats.answered}")
    print(f"Busy signals: {stats.busy_signals}")


if __name__ == "__main__":
    main()
