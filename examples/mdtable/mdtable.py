"""mdtable.py [--check] [--sum COL]: format Markdown pipe tables read from stdin.

Lines outside a table pass through unchanged.  A table is a header row, a delimiter row
(`---`, `:---`, `---:`, `:---:`) and body rows; every table is rewritten with each column
as wide as its widest cell (len(), at least 3), aligned as its delimiter says.
"""
import sys

LEFT = 0
RIGHT = 1
CENTER = 2

def text_of(raw):
    text = raw
    if text.endswith("\n"):
        text = text[:-1]
    if text.endswith("\r"):
        text = text[:-1]
    return text

def has_pipe(line):
    i = 0
    while i < len(line):
        if line[i] == "\\":
            i += 2
        elif line[i] == "|":
            return True
        else:
            i += 1
    return False

def split_cells(line):
    parts = []
    cur = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur += line[i:i + 2]
            i += 2
            continue
        if ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    stripped = line.strip()
    if stripped.startswith("|"):
        parts = parts[1:]
    if len(parts) > 0 and stripped.endswith("|"):
        k = 0
        j = len(stripped) - 2
        while j >= 0 and stripped[j] == "\\":
            k += 1
            j -= 1
        if k % 2 == 0:
            parts = parts[:-1]
    cells = []
    for p in parts:
        cells.append(p.strip())
    return cells

def is_delim_row(line):
    if not has_pipe(line):
        return False
    cells = split_cells(line)
    if len(cells) == 0:
        return False
    for cell in cells:
        t = cell.strip()
        a = 1 if t.startswith(":") else 0
        b = len(t) - 1 if len(t) > 1 and t.endswith(":") else len(t)
        if a >= b:
            return False
        for k in range(a, b):
            if t[k] != "-":
                return False
    return True

def is_int(text):
    if len(text) == 0:
        return False
    k = 1 if text[0] == "+" or text[0] == "-" else 0
    if k >= len(text):
        return False
    for c in range(k, len(text)):
        if text[c] < "0" or text[c] > "9":
            return False
    return True

def render(cells, widths, aligns, delim):
    out = "|"
    for c in range(len(cells)):
        if delim:
            w = widths[c]
            if aligns[c] == RIGHT:
                s = "-" * (w - 1) + ":"
            elif aligns[c] == CENTER:
                s = ":" + "-" * (w - 2) + ":"
            else:
                s = "-" * w
        else:
            s = cells[c]
            gap = widths[c] - len(s)
            if gap > 0:
                if aligns[c] == RIGHT:
                    s = " " * gap + s
                elif aligns[c] == CENTER:
                    left = gap // 2
                    s = " " * left + s + " " * (gap - left)
                else:
                    s = s + " " * gap
        out += " " + s + " |"
    return out

def format_table(header, delim_cells, body, sum_col):
    body = list(body)
    cols = len(header)
    for r in body:
        if len(r) > cols:
            cols = len(r)
    if sum_col + 1 > cols:
        cols = sum_col + 1
    rows = [header]
    rows.extend(body)
    padded = [list(r) + [""] * (cols - len(r)) for r in rows]
    header = padded[0]
    body = padded[1:]
    aligns = []
    for c in range(cols):
        t = delim_cells[c].strip() if c < len(delim_cells) else ""
        left = t.startswith(":")
        right = len(t) > 1 and t.endswith(":")
        if left and right:
            aligns.append(CENTER)
        elif right:
            aligns.append(RIGHT)
        else:
            aligns.append(LEFT)
    if sum_col >= 0:
        total = 0
        ok = True
        for r in body:
            if not is_int(r[sum_col]):
                ok = False
                break
            total += int(r[sum_col])
        row = [""] * cols
        row[sum_col] = str(total) if ok else "n/a"
        body.append(row)
    rows = [header]
    rows.extend(body)
    widths = [3] * cols
    for r in rows:
        for c in range(len(r)):
            if len(r[c]) > widths[c]:
                widths[c] = len(r[c])
    out = [render(header, widths, aligns, False), render(header, widths, aligns, True)]
    for r in body:
        out.append(render(r, widths, aligns, False))
    return out

def table_at(lines, i):
    if i + 1 >= len(lines):
        return None
    text = text_of(lines[i])
    nxt = text_of(lines[i + 1])
    if not has_pipe(text) or not is_delim_row(nxt):
        return None
    header = split_cells(text)
    delim = split_cells(nxt)
    if len(header) != len(delim):
        return None
    body = []
    j = i + 2
    while j < len(lines) and has_pipe(text_of(lines[j])):
        body.append(split_cells(text_of(lines[j])))
        j += 1
    return header, delim, body, j

def main():
    check = False
    sum_col = 0
    args = sys.argv
    i = 1
    while i < len(args):
        if args[i] == "--check":
            check = True
        elif args[i] == "--sum" and i + 1 < len(args):
            i += 1
            if not is_int(args[i]) or int(args[i]) < 1:
                sys.stderr.write("mdtable.py: --sum needs a positive column number\n")
                return 2
            sum_col = int(args[i])
        else:
            sys.stderr.write("usage: mdtable.py [--check] [--sum COL] < input.md\n")
            return 2
        i += 1

    lines = []
    for raw in sys.stdin:
        lines.append(raw)

    index = 0
    tables = 0
    code = 0
    fenced = False
    while index < len(lines):
        raw = lines[index]
        text = text_of(raw)
        found = None
        if text.strip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            found = table_at(lines, index)
        if found is None:
            if not check:
                sys.stdout.write(raw)
            index += 1
            continue
        header, delim, body, end = found
        tables += 1
        formatted = format_table(header, delim, body, sum_col - 1)
        if check:
            cols = len(header)
            for r in body:
                if len(r) > cols:
                    cols = len(r)
            if sum_col > cols:
                cols = sum_col
            sys.stdout.write("tables %d rows %d cols %d\n"
                             % (tables, 2 + len(body), cols))
            orig = []
            for k in range(index, end):
                orig.append(text_of(lines[k]))
            if orig != formatted:
                code = 1
        else:
            text = "\n".join(formatted)
            if lines[end - 1].endswith("\n"):
                text += "\n"
            sys.stdout.write(text)
        index = end
    return code

if __name__ == "__main__":
    sys.exit(main())
