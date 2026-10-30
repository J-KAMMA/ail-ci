"""Cases for chain_relax (see spec.md). cases(rng) -> (public, hidden, perf). Arguments only."""


def case(name, *args):
    return (name, b'', [str(a) for a in args])


def cases(rng):
    public = [
        case('small', 10, 3, 42),
        case('one_element', 1, 5, 7),
        case('bad_n', 0, 3, 42),
    ]
    hidden = [
        case('two_elements', 2, 7, 1),
        case('three_elements', 3, 4, 99),
        case('no_sweeps', 17, 0, 12346),
        case('one_sweep', 9, 1, 2024),
        case('two_sweeps', 9, 2, 2024),
        case('seed_zero', 50, 10, 0),
        case('seed_max', 33, 6, 18446744073709551615),
        ('leading_zeros', b'', ['0012', '003', '0042']),
        case('medium', 5000, 40, 777),
        case('many_sweeps_small', 7, 20000, 31337),
        case('odd_length', 101, 33, 5),
        case('even_length', 100, 34, 5),
        case('n_max_no_sweeps', 10000000, 0, 3),
        case('t_max_tiny', 1, 1000000, 11),
        case('n_too_big', 10000001, 1, 1),
        case('t_too_big', 5, 1000001, 1),
        case('seed_too_big', 5, 1, 18446744073709551616),
        ('negative', b'', ['5', '-1', '3']),
        ('plus_sign', b'', ['+5', '1', '3']),
        ('not_number', b'', ['5', '1', '3x']),
        ('empty_arg', b'', ['5', '', '3']),
        ('two_args', b'', ['5', '1']),
        ('four_args', b'', ['5', '1', '3', '4']),
        ('no_args', b'', []),
    ]
    for k in range(5):
        hidden.append(case('random%d' % k, rng.randrange(1, 300), rng.randrange(0, 60), rng.randrange(0, 1 << 64)))
    perf = case('perf', 300000, 200, 20261013)
    return public, hidden, perf
