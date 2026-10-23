# task: Find the key with the maximum value in a dictionary of city populations, breaking ties alphabetically.
from typing import Dict


def find_max_population_city(populations: Dict[str, int]) -> str:
    """Return the city with the maximum population; ties broken alphabetically (smallest name wins)."""
    if not populations:
        raise ValueError("populations dictionary is empty")
    return min(populations, key=lambda city: (-populations[city], city))


def main() -> None:
    city_populations: Dict[str, int] = {
        "Tokyo": 13960000,
        "Delhi": 16787941,
        "Shanghai": 24870895,
        "São Paulo": 12325232,
        "Mumbai": 12442373,
        "Cairo": 9539673,
        "Beijing": 21540000,
        "Dhaka": 8906039,
        "Osaka": 13000000,
        "New York": 8804190,
        "Karachi": 16051521,
        "Chicago": 2716000,
        "Lagos": 15388000,
        "Paris": 2161000,
        "Berlin": 3769495,
        "Madrid": 3223334,
        "Rome": 2872800,
        "Vienna": 1897491,
        "Oslo": 709037,
        "Dublin": 1388000,
    }

    top_city: str = find_max_population_city(city_populations)
    print(f"City with maximum population: {top_city} ({city_populations[top_city]:,})")

    # Tie-breaking demonstration
    tied: Dict[str, int] = {"Zurich": 500000, "Aarhus": 500000, "Milan": 300000}
    tie_winner: str = find_max_population_city(tied)
    print(f"Tie-break winner: {tie_winner} ({tied[tie_winner]:,})")


if __name__ == "__main__":
    main()
