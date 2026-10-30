"""Cases for berth_sim (see spec.md). cases(rng) -> (public, hidden, perf). Input on standard input."""

STDIN = True


def harbour(berths, ships):
    lines = ['%d %d' % (len(berths), len(ships))]
    lines += ['%d %d' % b for b in berths]
    lines += ['%d %d %d %d %d %d' % s for s in ships]
    return ('\n'.join(lines) + '\n').encode()


def random_harbour(rng, nb, ns, span, maxcargo=500, nops=5, ids_sparse=True):
    berths = [(rng.randrange(1, 4), rng.randrange(1, 60)) for _ in range(nb)]
    berths[rng.randrange(nb)] = (3, rng.randrange(1, 60))
    ids = rng.sample(range(10 ** 9 + 1), ns) if ids_sparse else list(range(ns))
    rng.shuffle(ids)
    ships = [(ids[k], rng.randrange(0, span + 1), rng.randrange(1, 4), rng.randrange(0, maxcargo + 1),
              rng.randrange(0, 10), rng.randrange(0, nops)) for k in range(ns)]
    return harbour(berths, ships)


def cases(rng):
    # berth 0 class 1 fast, berth 1 class 3 slow
    small = harbour([(1, 10), (3, 2)],
                    [(5, 0, 1, 30, 5, 1), (7, 0, 3, 10, 5, 2), (3, 1, 1, 10, 0, 1), (9, 2, 2, 4, 9, 2),
                     (1, 2, 1, 0, 9, 1), (8, 8, 1, 25, 1, 7)])
    public = [
        ('small', small, []),
        ('single_berth_queue', harbour([(3, 5)], [(10, 0, 1, 50, 3, 0), (11, 0, 1, 5, 3, 0), (12, 0, 2, 5, 2, 1),
                                                  (13, 1, 3, 5, 3, 0), (14, 0, 1, 5, 3, 0)]), []),
        ('random_small', random_harbour(rng, 3, 12, 40), []),
    ]
    hidden = [
        ('no_ships', harbour([(1, 1), (3, 7)], []), []),
        ('one_ship', harbour([(2, 3)], [(42, 100, 2, 10, 0, 0)]), []),
        ('zero_cargo', harbour([(3, 9)], [(1, 5, 1, 0, 0, 0), (2, 5, 1, 0, 0, 0), (3, 5, 1, 0, 0, 1)]), []),
        ('setup_same_operator', harbour([(3, 1)], [(1, 0, 1, 3, 0, 9), (2, 0, 1, 3, 1, 9), (3, 0, 1, 3, 2, 8),
                                                   (4, 0, 1, 3, 3, 9), (5, 0, 1, 3, 4, 9)]), []),
        ('operator_memory_per_berth', harbour([(3, 1), (3, 1)], [(1, 0, 1, 1, 0, 5), (2, 0, 1, 1, 0, 6), (3, 5, 1, 1, 0, 6),
                                                                  (4, 5, 1, 1, 0, 5)]), []),
        ('priority_then_arrival_then_id', harbour([(3, 100)], [(50, 0, 1, 1000, 0, 0), (40, 3, 1, 1, 5, 0), (30, 2, 1, 1, 5, 0),
                                                               (20, 2, 1, 1, 5, 0), (10, 4, 1, 1, 4, 0), (60, 4, 1, 1, 6, 0)]), []),
        ('small_berth_chooses_first', harbour([(3, 1), (1, 1)], [(1, 0, 1, 5, 0, 0), (2, 0, 3, 5, 1, 0)]), []),
        ('berth_number_order_within_class', harbour([(2, 1), (2, 50), (2, 7)], [(1, 0, 1, 100, 0, 0), (2, 0, 2, 100, 0, 0)]), []),
        ('big_ship_waits', harbour([(1, 10), (1, 10), (3, 1)], [(1, 0, 1, 1000, 0, 0), (2, 0, 3, 10, 0, 0), (3, 1, 3, 10, 0, 0),
                                                                (4, 1, 1, 10, 9, 0)]), []),
        ('depart_and_arrive_same_minute', harbour([(3, 1)], [(1, 0, 1, 6, 0, 0), (2, 10, 1, 1, 9, 0), (3, 10, 1, 1, 9, 1),
                                                             (4, 9, 1, 1, 9, 2)]), []),
        ('ceil_division', harbour([(3, 7)], [(1, 0, 1, 1, 0, 0), (2, 0, 1, 7, 0, 0), (3, 0, 1, 8, 0, 0), (4, 0, 1, 14, 0, 0),
                                             (5, 0, 1, 15, 0, 0)]), []),
        ('extreme_values', harbour([(3, 1), (3, 1000)], [(1000000000, 1000000000, 3, 1000000, 9, 1000000),
                                                        (0, 1000000000, 3, 1000000, 9, 1000000), (5, 0, 1, 1000000, 0, 0)]), []),
        ('unsorted_input', harbour([(1, 3), (2, 3), (3, 3)], [(9, 30, 1, 9, 1, 1), (8, 0, 3, 9, 1, 1), (7, 15, 2, 9, 1, 1),
                                                              (6, 0, 1, 9, 1, 1), (5, 15, 3, 9, 0, 2)]), []),
        ('wait_max_tie', harbour([(3, 1)], [(5, 0, 1, 10, 0, 0), (9, 0, 1, 1, 1, 1), (3, 13, 1, 1, 0, 1)]), []),
        ('many_berths_few_ships', random_harbour(rng, 2000, 30, 100), []),
    ]
    for k in range(6):
        hidden.append(('random%d' % k, random_harbour(rng, rng.randrange(1, 8), rng.randrange(1, 80),
                                                      rng.choice([10, 200, 5000])), []))
    hidden.append(('random_busy', random_harbour(rng, 6, 3000, 20000, maxcargo=300, ids_sparse=False), []))
    hidden.append(('random_calm', random_harbour(rng, 20, 2000, 10 ** 9, maxcargo=10 ** 6), []))
    perf = ('perf', perf_harbour(rng), [])
    return public, hidden, perf


def perf_harbour(rng, nb=64, ns=3000000):
    berths = [(1 + (i % 3), rng.randrange(20, 80)) for i in range(nb)]
    ids = list(range(0, 3 * ns, 3))
    rng.shuffle(ids)
    lines = ['%d %d' % (nb, ns)] + ['%d %d' % b for b in berths]
    span = ns          # about one arrival per minute: roughly 70% of the harbour capacity
    randrange = rng.randrange
    for k in range(ns):
        lines.append('%d %d %d %d %d %d' % (ids[k], randrange(0, span), randrange(1, 4), randrange(0, 4000),
                                            randrange(0, 10), randrange(0, 40)))
    return ('\n'.join(lines) + '\n').encode()
