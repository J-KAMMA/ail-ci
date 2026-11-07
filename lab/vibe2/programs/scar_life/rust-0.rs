use std::io::{self, Read, Write};

fn parse_dim(line: &[u8], i: &mut usize) -> Option<usize> {
    let start = *i;
    if start >= line.len() {
        return None;
    }
    if line[start] < b'1' || line[start] > b'9' {
        return None;
    }

    let mut value = 0usize;
    let mut j = start;
    while j < line.len() && line[j].is_ascii_digit() {
        value = value
            .checked_mul(10)?
            .checked_add((line[j] - b'0') as usize)?;
        j += 1;
    }

    if value < 1 || value > 4096 {
        return None;
    }

    *i = j;
    Some(value)
}

fn parse_input(data: &[u8]) -> Option<(usize, usize, Vec<u8>)> {
    let newline = data.iter().position(|&b| b == b'\n')?;
    let header = &data[..newline];

    let mut i = 0usize;
    let w = parse_dim(header, &mut i)?;
    if i >= header.len() || header[i] != b' ' {
        return None;
    }
    i += 1;

    let h = parse_dim(header, &mut i)?;
    if i != header.len() {
        return None;
    }

    let mut pos = newline + 1;
    let mut grid = Vec::with_capacity(w * h);

    for y in 0..h {
        if pos + w > data.len() {
            return None;
        }

        for k in 0..w {
            let value = match data[pos + k] {
                b'.' => 0u8,
                b'o' => 1u8,
                _ => return None,
            };
            grid.push(value);
        }
        pos += w;

        if y + 1 < h {
            if pos >= data.len() || data[pos] != b'\n' {
                return None;
            }
            pos += 1;
        } else if pos < data.len() {
            if data[pos] == b'\n' && pos + 1 == data.len() {
                pos += 1;
            } else {
                return None;
            }
        }
    }

    if pos != data.len() {
        return None;
    }

    Some((w, h, grid))
}

fn fill_codes(segment: &[u8], set: &mut [bool; 13]) -> bool {
    let mut previous: Option<u8> = None;

    for &c in segment {
        let code = match c {
            b'0'..=b'9' => c - b'0',
            b'A' => 10,
            b'B' => 11,
            b'C' => 12,
            _ => return false,
        };

        if let Some(prev) = previous {
            if code <= prev {
                return false;
            }
        }

        previous = Some(code);
        set[code as usize] = true;
    }

    true
}

fn parse_rule(rule: &str) -> Option<([bool; 13], [bool; 13])> {
    let bytes = rule.as_bytes();

    if bytes.len() < 3 || bytes[0] != b'B' {
        return None;
    }

    let slash = bytes.iter().position(|&b| b == b'/')?;
    if slash + 1 >= bytes.len() || bytes[slash + 1] != b'S' {
        return None;
    }

    let mut born = [false; 13];
    let mut survive = [false; 13];

    if !fill_codes(&bytes[1..slash], &mut born) {
        return None;
    }
    if !fill_codes(&bytes[slash + 2..], &mut survive) {
        return None;
    }

    Some((born, survive))
}

fn parse_gens(value: &str) -> Option<usize> {
    if value.is_empty() {
        return None;
    }

    let mut result = 0usize;
    for &c in value.as_bytes() {
        if !c.is_ascii_digit() {
            return None;
        }

        result = result
            .checked_mul(10)?
            .checked_add((c - b'0') as usize)?;

        if result > 100_000 {
            return None;
        }
    }

    Some(result)
}

fn run() -> Option<()> {
    let args: Vec<String> = std::env::args_os()
        .skip(1)
        .map(|arg| arg.into_string().ok())
        .collect::<Option<Vec<_>>>()?;

    if args.len() != 2 {
        return None;
    }

    let (born, survive) = parse_rule(&args[0])?;
    let generations = parse_gens(&args[1])?;

    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input).ok()?;

    let (w, h, mut grid) = parse_input(&input)?;
    let cells = w * h;

    let mut next = vec![0u8; cells];
    let mut vertical = vec![0u8; w];
    let mut combined = vec![0u8; w];

    let stdout = io::stdout();
    let mut out = io::BufWriter::with_capacity(1 << 20, stdout.lock());

    for generation in 1..=generations {
        let mut alive_count = 0usize;
        let mut scar_count = 0usize;

        for y in 0..h {
            let up_y = if y == 0 { h - 1 } else { y - 1 };
            let down_y = if y + 1 == h { 0 } else { y + 1 };

            let up_offset = up_y * w;
            let down_offset = down_y * w;
            let current_offset = y * w;

            for x in 0..w {
                let v = ((grid[up_offset + x] == 1) as u8)
                    + ((grid[down_offset + x] == 1) as u8);
                vertical[x] = v;

                let current = if grid[current_offset + x] == 1 {
                    2u8
                } else {
                    0u8
                };
                combined[x] = current + v;
            }

            for x in 0..w {
                let left = if x == 0 { w - 1 } else { x - 1 };
                let right = if x + 1 == w { 0 } else { x + 1 };

                let weight =
                    (2 * vertical[x] + combined[left] + combined[right]) as usize;

                let old = grid[current_offset + x];
                let new_state = if old == 1 {
                    if survive[weight] {
                        1u8
                    } else {
                        2u8
                    }
                } else if old == 0 {
                    if born[weight] {
                        1u8
                    } else {
                        0u8
                    }
                } else {
                    0u8
                };

                next[current_offset + x] = new_state;

                if new_state == 1 {
                    alive_count += 1;
                } else if new_state == 2 {
                    scar_count += 1;
                }
            }
        }

        std::mem::swap(&mut grid, &mut next);

        writeln!(out, "{} {} {}", generation, alive_count, scar_count).ok()?;
    }

    for y in 0..h {
        let start = y * w;
        let mut line = Vec::with_capacity(w + 1);

        for &state in &grid[start..start + w] {
            line.push(match state {
                0 => b'.',
                1 => b'o',
                _ => b'x',
            });
        }

        line.push(b'\n');
        out.write_all(&line).ok()?;
    }

    out.flush().ok()?;
    Some(())
}

fn main() {
    if run().is_none() {
        std::process::exit(1);
    }
}
