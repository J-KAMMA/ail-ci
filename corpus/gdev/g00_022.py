# task: Write a script that parses hardcoded key=value configuration text into a dictionary and prints it sorted by key.
from typing import Dict


CONFIG_TEXT: str = """
# Application configuration
app_name = Demo Service
version=1.4.2
debug = false

# Server settings
host=127.0.0.1
port = 8080
timeout=30   # seconds
# Feature flags
feature.cache = true
feature.metrics=false
empty_value =
"""


def parse_config(text: str) -> Dict[str, str]:
    """Parse key=value lines into a dictionary, ignoring comments and blanks."""
    result: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def main() -> None:
    config: Dict[str, str] = parse_config(CONFIG_TEXT)
    for key in sorted(config):
        print(f"{key} = {config[key]!r}")


if __name__ == "__main__":
    main()
