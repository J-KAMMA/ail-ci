# task: Write a script that extracts all hashtags from a hardcoded social media post and prints them in order of appearance without duplicates.
import re


POST: str = (
    "Just finished our first hike of the season! #Hiking #Nature #hiking "
    "The views were incredible. #Sunset #nature #Adventure\n"
    "Don't forget to check out the new blog post at example.com/trip#top "
    "#Photography #OutdoorLife #Hiking #sunset #Blessed #Travel_2024 "
    "Email me at test#1 or chat with friends #Friends!"
)

HASHTAG_PATTERN: re.Pattern[str] = re.compile(r"(?<![\w&])#(\w+)")


def extract_hashtags(text: str) -> list[str]:
    """Return hashtags (without the leading '#') in order of first appearance."""
    matches: list[str] = HASHTAG_PATTERN.findall(text)
    # dict.fromkeys preserves insertion order, so this removes duplicates
    # while keeping the first occurrence of each tag.
    return list(dict.fromkeys(matches))


def main() -> None:
    hashtags: list[str] = extract_hashtags(POST)
    for tag in hashtags:
        print(f"#{tag}")


if __name__ == "__main__":
    main()
