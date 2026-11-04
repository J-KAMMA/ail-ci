# task: Write a script that uses re.findall to extract all hashtags from a hardcoded tweet list and prints a frequency count of each tag sorted by count.
import re
from collections import Counter

TWEETS: list[str] = [
    "Just finished my first marathon! #running #fitness #motivation",
    "Coffee and code all morning. #coding #python #coffee",
    "Beautiful sunset at the beach tonight #sunset #nature #photography",
    "Learning regex today, it's getting easier! #python #coding #regex",
    "Team meeting moved to 3pm. #work #teamwork",
    "Trying a new recipe for dinner #cooking #food #homemade",
    "Who else is excited for the #python conference this year? #PYTHON #conference",
    "Rainy day, perfect for reading a good book #reading #books #coffee",
    "Morning run done before sunrise #running #fitness #nature",
    "Shipped a new feature to production! #coding #devlife #python",
    "No hashtags in this one, just text.",
    "Mixing #Photography and #coding in a weekend project #Coding #photography",
    "Wrote unit tests for the parser #testing #coding #python3",
    "Dinner with friends at the new place downtown #food #friends",
    "Edge case: a lone # sign and a hash#inside should be handled #regex",
]

HASHTAG_PATTERN: re.Pattern[str] = re.compile(r"(?<!\w)#(\w+)")


def extract_hashtags(tweet: str) -> list[str]:
    """Return all hashtags in a tweet, lowercased, without the leading '#'."""
    return [tag.lower() for tag in HASHTAG_PATTERN.findall(tweet)]


def count_hashtags(tweets: list[str]) -> Counter[str]:
    """Count hashtag occurrences across all tweets."""
    counts: Counter[str] = Counter()
    for tweet in tweets:
        counts.update(extract_hashtags(tweet))
    return counts


def main() -> None:
    counts = count_hashtags(TWEETS)

    # Sort by count descending, then tag name ascending for deterministic output.
    ordered: list[tuple[str, int]] = sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )

    print(f"Total hashtags found: {sum(counts.values())}")
    print(f"Unique hashtags: {len(counts)}")
    print()
    print(f"{'Hashtag':<20}{'Count':>5}")
    print("-" * 25)
    for tag, count in ordered:
        print(f"#{tag:<19}{count:>5}")


if __name__ == "__main__":
    main()
