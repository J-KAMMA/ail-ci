"""Cases for scar_life (see spec.md). cases(rng) -> (public, hidden, perf). Grid on standard input."""

STDIN = True

PERF_RULE = 'B35/S2468A'


def grid(rows, final=True):
    h = len(rows)
    w = len(rows[0])
    return ('%d %d\n' % (w, h) + '\n'.join(rows) + ('\n' if final else '')).encode()


def random_grid(rng, w, h, p):
    return grid([''.join('o' if rng.random() < p else '.' for _ in range(w)) for _ in range(h)])


GLIDERISH = ['..........',
             '...o......',
             '....o.....',
             '..ooo.....',
             '..........',
             '......oo..',
             '......oo..',
             '..........']


def cases(rng):
    public = [
        ('small', grid(GLIDERISH), ['B35/S2468A', '5']),
        ('one_cell', grid(['o']), ['B/SC', '3']),
        ('bad_rule', grid(GLIDERISH), ['B64/S2357', '5']),
    ]
    hidden = [
        ('gens_zero', grid(GLIDERISH), ['B3/S23', '0']),
        ('gens_leading_zeros', grid(GLIDERISH), ['B46/S2357', '0007']),
        ('empty_rule', grid(GLIDERISH), ['B/S', '3']),
        ('born_zero', grid(['....', '....', '....']), ['B0/S', '4']),
        ('all_codes', grid(GLIDERISH), ['B0123456789ABC/S0123456789ABC', '3']),
        ('high_codes', random_grid(rng, 9, 7, 0.6), ['B9ABC/SABC', '6']),
        ('one_cell_dead', grid(['.']), ['B0/S', '4']),
        ('one_cell_alive_stays', grid(['o']), ['B/SC', '2']),
        ('one_cell_alive_dies', grid(['o']), ['B/SB', '3']),
        ('width_one', grid(['o', '.', 'o', 'o', '.']), ['B2468/S468C', '6']),
        ('height_one', grid(['o.oo.o..o']), ['B2468/S468C', '6']),
        ('width_two', grid(['o.', '.o', 'oo', '..']), ['B135/S2467', '6']),
        ('two_by_two', grid(['o.', '..']), ['B12/S', '5']),
        ('torus_wrap', grid(['o......o', '........', '........', 'o......o']), ['B3456/S12345', '4']),
        ('scars_block_birth', grid(['.....', '.ooo.', '.....', '.....']), ['B2/S', '4']),
        ('no_final_newline', grid(GLIDERISH, final=False), ['B46/S2357', '3']),
        ('random_a', random_grid(rng, 30, 20, 0.35), ['B46/S2357', '25']),
        ('random_b', random_grid(rng, 17, 41, 0.5), ['B5A/S34', '30']),
        ('random_c', random_grid(rng, 64, 3, 0.4), ['B3/S23', '20']),
        ('random_d', random_grid(rng, 50, 50, 0.2), ['B357/S1468', '40']),
        ('random_e', random_grid(rng, 33, 29, 0.3), ['B4/S24689B', '35']),
        ('gens_max', grid(['o.', '..']), ['B1/S', '100000']),
        # errors
        ('rule_lowercase', grid(GLIDERISH), ['b3/s23', '1']),
        ('rule_lower_code', grid(GLIDERISH), ['B3a/S23', '1']),
        ('rule_repeat', grid(GLIDERISH), ['B33/S23', '1']),
        ('rule_code_D', grid(GLIDERISH), ['B3D/S23', '1']),
        ('rule_missing_slash', grid(GLIDERISH), ['B3S23', '1']),
        ('rule_extra', grid(GLIDERISH), ['B3/S23/', '1']),
        ('rule_swapped', grid(GLIDERISH), ['S23/B3', '1']),
        ('gens_too_big', grid(GLIDERISH), ['B3/S23', '100001']),
        ('gens_negative', grid(GLIDERISH), ['B3/S23', '-1']),
        ('gens_plus', grid(GLIDERISH), ['B3/S23', '+1']),
        ('gens_empty', grid(GLIDERISH), ['B3/S23', '']),
        ('no_args', grid(GLIDERISH), []),
        ('three_args', grid(GLIDERISH), ['B3/S23', '1', '1']),
        ('empty_input', b'', ['B3/S23', '1']),
        ('header_only', b'3 1\n', ['B3/S23', '1']),
        ('header_leading_zero', b'03 1\no.o\n', ['B3/S23', '1']),
        ('header_zero', b'0 1\n\n', ['B3/S23', '1']),
        ('header_too_big', b'4097 1\n' + b'.' * 4097 + b'\n', ['B3/S23', '1']),
        ('header_two_spaces', b'3  1\no.o\n', ['B3/S23', '1']),
        ('short_row', b'3 2\no.o\no.\n', ['B3/S23', '1']),
        ('long_row', b'3 2\no.o\no..o\n', ['B3/S23', '1']),
        ('too_few_rows', b'3 3\no.o\no..\n', ['B3/S23', '1']),
        ('too_many_rows', b'3 1\no.o\no..\n', ['B3/S23', '1']),
        ('trailing_empty_line', b'3 1\no.o\n\n', ['B3/S23', '1']),
        ('crlf', b'3 1\r\no.o\r\n', ['B3/S23', '1']),
        ('bad_char_x', b'3 1\nox.\n', ['B3/S23', '1']),
        ('bad_char_O', b'3 1\nO..\n', ['B3/S23', '1']),
        ('max_width_row', grid(['o.' * 2048]), ['B2/S1', '3']),
    ]
    perf = ('perf', random_grid(rng, 2048, 2048, 0.3), [PERF_RULE, '1000'])
    return public, hidden, perf
