# task: Print the quarter of the year (Q1 to Q4) for each month of 2024 derived from datetime objects.
from datetime import date


def quarter_of(d: date) -> str:
    return f"Q{(d.month - 1) // 3 + 1}"


def main() -> None:
    for month in range(1, 13):
        first_day = date(2024, month, 1)
        print(f"{first_day.strftime('%B')} 2024: {quarter_of(first_day)}")


if __name__ == "__main__":
    main()
