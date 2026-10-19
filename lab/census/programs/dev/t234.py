import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    h: int = int(data[0])
    w: int = int(data[1])
    rows: list[str] = data[2:2 + h]
    # Pad in case of missing or short rows.
    grid: list[str] = [
        (rows[i] if i < len(rows) else "").ljust(w, ".")[:w] for i in range(h)
    ]

    out_lines: list[str] = []
    for r in range(h):
        line_chars: list[str] = []
        for c in range(w):
            count: int = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr: int = r + dr
                    nc: int = c + dc
                    if 0 <= nr < h and 0 <= nc < w and grid[nr][nc] == "#":
                        count += 1
            line_chars.append(str(count))
        out_lines.append("".join(line_chars))

    sys.stdout.write("\n".join(out_lines) + ("\n" if out_lines else ""))


if __name__ == "__main__":
    main()
