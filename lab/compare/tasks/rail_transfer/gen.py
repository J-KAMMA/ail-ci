"""Cases for rail_transfer (see spec.md). cases(rng) -> (public, hidden, perf). Network on standard input."""

STDIN = True


def net(n, xfer, segs, queries):
    lines = ['%d %d %d' % (n, len(segs), len(queries)), ' '.join(map(str, xfer))]
    lines += ['%d %d %d %d' % s for s in segs]
    lines += ['%d %d' % qq for qq in queries]
    return ('\n'.join(lines) + '\n').encode()


def random_net(rng, n, nlines, line_len, extra, nq, maxt=50, maxx=30):
    xfer = [rng.randrange(0, maxx + 1) for _ in range(n)]
    segs = []
    for line in range(nlines):
        lid = rng.randrange(0, 100000) if rng.random() < 0.5 else line
        cur = rng.randrange(n)
        for _ in range(rng.randrange(1, line_len + 1)):
            nxt = rng.randrange(n) if rng.random() < 0.3 else (cur + rng.randrange(-5, 6)) % n
            segs.append((cur, nxt, lid, rng.randrange(0, maxt + 1)))
            cur = nxt
    for _ in range(extra):
        segs.append((rng.randrange(n), rng.randrange(n), rng.randrange(0, nlines + 1), rng.randrange(0, maxt + 1)))
    rng.shuffle(segs)
    queries = [(rng.randrange(n), rng.randrange(n)) for _ in range(nq)]
    return net(n, xfer, segs, queries)


def cases(rng):
    # 0 -A- 1 -A- 2 -A- 3 ; 1 -B- 4 -B- 3 ; transfer at 1 costs 5
    small = net(6, [0, 5, 0, 0, 1, 0],
                [(0, 1, 7, 10), (1, 2, 7, 10), (2, 3, 7, 10), (1, 4, 9, 3), (4, 3, 9, 3), (5, 5, 2, 1)],
                [(0, 3), (3, 0), (0, 4), (2, 2), (0, 5), (5, 5), (4, 0)])
    public = [
        ('small', small, []),
        ('tie_on_time', net(4, [0, 0, 0, 0], [(0, 1, 1, 5), (1, 3, 2, 5), (0, 2, 3, 6), (2, 3, 3, 4)], [(0, 3), (3, 0)]), []),
        ('random_small', random_net(rng, 12, 4, 6, 3, 8), []),
    ]
    hidden = [
        ('no_queries', net(3, [1, 2, 3], [(0, 1, 0, 1)], []), []),
        ('no_segments', net(3, [1, 2, 3], [], [(0, 1), (2, 2), (1, 0)]), []),
        ('single_station', net(1, [7], [(0, 0, 4, 3)], [(0, 0)]), []),
        ('isolated_station', net(4, [0, 0, 0, 0], [(0, 1, 1, 1), (1, 2, 1, 1)], [(0, 3), (3, 0), (0, 2), (3, 3)]), []),
        ('stay_on_line_back_and_forth', net(4, [0, 100, 0, 0],
                                            [(0, 1, 1, 10), (1, 2, 1, 10), (2, 1, 2, 1), (1, 3, 2, 1)],
                                            [(0, 3), (3, 0), (0, 2)]), []),
        ('transfer_cost_at_start_free', net(3, [1000, 0, 1000], [(0, 1, 1, 5), (0, 1, 2, 1), (1, 2, 2, 1)], [(0, 2), (2, 0)]), []),
        ('zero_times', net(5, [0, 0, 0, 0, 0], [(0, 1, 1, 0), (1, 2, 2, 0), (2, 3, 3, 0), (0, 3, 4, 0), (3, 4, 4, 0)],
                           [(0, 4), (1, 4), (4, 1)]), []),
        ('parallel_segments', net(3, [2, 2, 2], [(0, 1, 1, 9), (0, 1, 2, 4), (0, 1, 1, 3), (1, 2, 2, 1), (1, 2, 1, 5)],
                                  [(0, 2), (2, 0)]), []),
        ('same_line_rejoin', net(5, [0, 0, 0, 0, 0], [(0, 1, 5, 1), (1, 2, 6, 1), (2, 3, 5, 1), (3, 4, 5, 1)], [(0, 4)]), []),
        ('fewer_boardings_win_tie', net(4, [0, 0, 0, 0], [(0, 1, 1, 2), (1, 2, 2, 2), (2, 3, 3, 2), (0, 3, 9, 6)],
                                        [(0, 3), (3, 0)]), []),
        ('self_loops_only', net(2, [0, 0], [(0, 0, 1, 0), (1, 1, 1, 0)], [(0, 1)]), []),
        ('big_numbers', net(3, [1000, 1000, 1000], [(0, 1, 99999, 100000), (1, 2, 0, 100000), (1, 2, 99999, 100000)],
                            [(0, 2), (2, 0)]), []),
        ('line_ids_sparse', net(4, [3, 1, 4, 1], [(0, 1, 99999, 2), (1, 2, 0, 2), (2, 3, 50000, 2), (3, 0, 99999, 9)],
                                [(0, 2), (1, 3), (3, 1), (2, 0)]), []),
    ]
    for k in range(6):
        hidden.append(('random%d' % k, random_net(rng, rng.randrange(5, 60), rng.randrange(1, 12), 12,
                                                  rng.randrange(0, 20), rng.randrange(1, 30)), []))
    hidden.append(('random_medium', random_net(rng, 3000, 150, 60, 500, 40, maxt=1000, maxx=200), []))
    hidden.append(('random_zero_xfer', random_net(rng, 500, 40, 30, 50, 30, maxx=0), []))
    perf = ('perf', random_net(rng, 100000, 4000, 80, 20000, 25, maxt=600, maxx=120), [])
    return public, hidden, perf
