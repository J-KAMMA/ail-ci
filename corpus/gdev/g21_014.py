# task: Use json.dumps with default=str to serialize a dictionary containing a Decimal and a Path object, then print the output.
import json
from decimal import Decimal
from pathlib import Path


def main() -> None:
    data: dict[str, object] = {
        "price": Decimal("19.99"),
        "location": Path("/var/data/report.txt"),
    }
    print(json.dumps(data, default=str))


if __name__ == "__main__":
    main()
