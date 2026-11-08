"""Driver for csv_parse: parse a generated CSV document."""
import csv_parse as m

ROW = '1,2,3,"four five",6,7,8,9\n'
ROWS = 350000


def main() -> None:
    text = ROW * ROWS
    lines = m.split_lines(text)
    total = 0
    fields = 0
    chars = 0
    for ln in lines:
        fields += m.count_fields(ln)
        chars += m.field_chars(ln)
    print("lines", len(lines))
    print("fields", fields)
    print("chars", chars)
    print("column2", m.sum_column(text, 2))
    print("maxlen", m.max_field_len(text))
    print("quotes", m.quote_count(text))
    print("sum", total)


main()
