"""Cases for grid_bfs (see spec.md). cases(rng) -> (public, hidden, perf). Grid on stdin."""

STDIN = True


def encode(H, W, rows, queries):
    out = ['%d %d %d\n' % (H, W, len(queries))]
    for row in rows:
        out.append(row + '\n')
    for q in queries:
        out.append('%d %d %d %d\n' % q)
    return ''.join(out).encode()


def random_rows(rng, H, W, wall_percent):
    return [''.join(rng.choices('.#', weights=(100 - wall_percent, wall_percent), k=W))
            for _ in range(H)]


def public_cases():
    basic = [
        '.......',
        '.#.#.#.',
        '.#...#.',
        '.#.#...',
        '.......',
    ]
    basic_q = [(0, 0, 4, 6), (1, 0, 1, 2), (4, 6, 2, 3), (3, 0, 0, 6)]
    unreachable = [
        '.....',
        '.###.',
        '.#.#.',
        '.###.',
        '.....',
    ]
    unreachable_q = [(0, 0, 2, 2), (0, 4, 2, 2), (4, 4, 2, 2), (2, 2, 0, 0)]
    start_wall = [
        '....',
        '.#..',
        '..#.',
        '....',
    ]
    start_wall_q = [(1, 1, 0, 0), (2, 2, 3, 3), (0, 0, 1, 1), (3, 3, 3, 3)]
    return [
        ('basic', encode(5, 7, basic, basic_q), []),
        ('unreachable', encode(5, 5, unreachable, unreachable_q), []),
        ('start_wall', encode(4, 4, start_wall, start_wall_q), []),
    ]


def one_by_one():
    return encode(1, 1, ['.'], [(0, 0, 0, 0)])


def one_by_2000(rng):
    row = ''.join(rng.choices('.#', weights=(90, 10), k=2000))
    q = [(0, 0, 0, 1999), (0, 1999, 0, 0), (0, 7, 0, 7), (0, 500, 0, 501)]
    return encode(1, 2000, [row], q)


def same_cell():
    rows = ['.....', '..#..', '.....', '.#.#.', '.....']
    q = [(0, 0, 0, 0), (1, 0, 1, 0), (1, 2, 1, 2), (4, 4, 4, 4), (2, 2, 0, 0)]
    return encode(5, 5, rows, q)


def q_zero():
    rows = ['....', '.#..', '....']
    return encode(3, 4, rows, [])


def random_small(rng):
    rows = random_rows(rng, 8, 13, 25)
    q = [(rng.randrange(8), rng.randrange(13), rng.randrange(8), rng.randrange(13))
         for _ in range(5)]
    return encode(8, 13, rows, q)


def random_medium(rng):
    rows = random_rows(rng, 60, 90, 28)
    q = [(rng.randrange(60), rng.randrange(90), rng.randrange(60), rng.randrange(90))
         for _ in range(8)]
    return encode(60, 90, rows, q)


def perf_case(rng):
    H = 2000
    W = 2000
    rows = random_rows(rng, H, W, 30)
    q = [(rng.randrange(H), rng.randrange(W), rng.randrange(H), rng.randrange(W))
         for _ in range(20)]
    return encode(H, W, rows, q)


def cases(rng):
    public = public_cases()
    hidden = [
        ('one_by_one', one_by_one(), []),
        ('one_by_2000', one_by_2000(rng), []),
        ('same_cell', same_cell(), []),
        ('q_zero', q_zero(), []),
        ('random_small', random_small(rng), []),
        ('random_medium', random_medium(rng), []),
    ]
    perf = ('perf', perf_case(rng), [])
    return public, hidden, perf
