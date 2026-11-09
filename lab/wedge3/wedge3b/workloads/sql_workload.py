"""Split and format a large SQL file with sqlparse (pure Python) or sqlglot[rs] (Rust lexer).

The two formatters disagree about indentation, keyword case and spaces around operators, so the
workload compares a normalised form: lowercase with all whitespace and statement terminators
removed.  On the generated corpus (plain SELECT/INSERT/UPDATE/DELETE, no quoting) that normal form
is identical for both libraries, while the formatting work is real for both.
"""
import os

STATEMENTS = 2000
SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'queries.sql')
CITIES = ('amsterdam', 'berlin', 'lisbon', 'oslo', 'prague', 'rome')


def make_sql():
    rows = []
    for i in range(STATEMENTS):
        kind = i % 4
        r = i % 97
        if kind == 0:
            rows.append(
                "SELECT c0, c1, c2 FROM t%d WHERE c0 = %d AND c2 = '%s';"
                % (r, i % 13, CITIES[i % len(CITIES)]))
        elif kind == 1:
            rows.append(
                "INSERT INTO t%d (c0, c1, c2) VALUES (%d, '%s-%d', %d);"
                % (r, i, CITIES[i % len(CITIES)], r, i * 3 % 1000))
        elif kind == 2:
            rows.append(
                "UPDATE t%d SET c1 = %d WHERE c0 = %d AND c1 = '%s';"
                % (r, i * 7 % 1000, r, CITIES[i % len(CITIES)]))
        else:
            rows.append(
                "DELETE FROM t%d WHERE c0 = %d;" % (r, i % 211))
    return '\n'.join(rows) + '\n'


def ensure_file():
    if not os.path.exists(SQL_FILE):
        with open(SQL_FILE, 'w', encoding='utf-8') as handle:
            handle.write(make_sql())


def normalise(text):
    return ''.join(text.split()).replace(';', '').lower()


def fnv(text, value=1469598103934665603):
    for ch in text:
        value = ((value ^ ord(ch)) * 1099511628211) & ((1 << 64) - 1)
    return value


def run_sqlparse(text):
    import sqlparse
    parts = sqlparse.split(text)
    formatted = '\n'.join(
        sqlparse.format(part, reindent=True, keyword_case='upper') for part in parts)
    return parts, formatted


def run_sqlglot(text):
    import sqlglot
    expressions = sqlglot.parse(text, read=None)
    formatted = '\n'.join(expr.sql(pretty=True) for expr in expressions)
    return expressions, formatted


def main():
    ensure_file()
    with open(SQL_FILE, encoding='utf-8') as handle:
        text = handle.read()
    try:
        import sqlglot  # noqa: F401
    except ImportError:
        parts, formatted = run_sqlparse(text)
    else:
        parts, formatted = run_sqlglot(text)
    flat = normalise(formatted)
    print('statements', len(parts))
    print('normalised_chars', len(flat))
    print('normalised_hash', fnv(flat))
    print('semicolons', text.count(';'))


if __name__ == '__main__':
    main()
