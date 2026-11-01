# task: Validate embedded CSV rows against an expected field count and print the line numbers and reasons for each invalid row.
import csv
import io
from typing import NamedTuple

EXPECTED_FIELDS = 3

# Embedded sample data (no external input is read).
# Line 1: header; line 2: valid quoted comma; line 3: too few fields;
# line 4: too many fields; line 5: blank line; lines 6-7: valid multi-line field;
# line 8: malformed quoting; line 9: unterminated quote running to end of data.
EMBEDDED_CSV = """\
name,age,city
Alice,30,"New York, NY"
Bob,25
Carol,41,Boston,extra

Frank,50,"Multi
line"
Gina,"Ok"x,Miami
Hank,"open,Reno
"""


class Problem(NamedTuple):
    line: int
    reason: str


def validate_csv(text: str, expected: int) -> tuple[int, list[Problem]]:
    """Validate CSV text, returning the number of parsed records and any problems."""
    reader = csv.reader(io.StringIO(text), strict=True)
    problems: list[Problem] = []
    records = 0
    last_line = 0  # physical line number of the last line consumed

    while True:
        start_line = last_line + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            last_line = reader.line_num
            problems.append(Problem(start_line, f"CSV syntax error: {exc}"))
            continue

        last_line = reader.line_num
        records += 1

        if not row:
            problems.append(
                Problem(start_line, f"blank line (0 fields, expected {expected})")
            )
        elif len(row) != expected:
            problems.append(
                Problem(
                    start_line,
                    f"expected {expected} fields, found {len(row)}",
                )
            )

    return records, problems


def main() -> None:
    records, problems = validate_csv(EMBEDDED_CSV, EXPECTED_FIELDS)

    print(f"Expected field count: {EXPECTED_FIELDS}")
    print(f"Successfully parsed records: {records}")
    print(f"Invalid rows: {len(problems)}")
    for problem in problems:
        print(f"Line {problem.line}: {problem.reason}")


if __name__ == "__main__":
    main()
