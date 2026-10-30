"""Cases for tally_lang (see spec.md). cases(rng) -> (public, hidden, perf)."""

A = ['{input}']

EXAMPLE = '''set x = 10
loop 3        ; three times
  set x = x * 2 + 1
  when x > 50
    out x, x ~ 1, #x
    break
  end
end
out x <> 7 >< 3, -1, !0
'''


def script(*lines, final=True):
    return ('\n'.join(lines) + ('\n' if final else '')).encode()


def rand_expr(rng, names, depth):
    r = rng.random()
    if depth <= 0 or r < 0.3:
        if names and rng.random() < 0.6:
            return rng.choice(names)
        return str(rng.choice([0, 1, 2, 3, 7, 31, 32, 33, 100, 255, 65535, 65536, 2147483648, 4294967295,
                               rng.randrange(0, 1 << 32), rng.randrange(0, 1000)]))
    if r < 0.42:
        return rng.choice(['-', '#', '!', '- ', '!-']) + rand_expr(rng, names, depth - 1)
    if r < 0.5:
        return '(' + rand_expr(rng, names, depth - 1) + ')'
    op = rng.choice(['+', '-', '*', '/', '%', '~', '<>', '><', '+', '*', '-', '~'])
    left = rand_expr(rng, names, depth - 1)
    right = rand_expr(rng, names, depth - 1)
    if op in ('/', '%') and rng.random() < 0.8:
        right = '(' + right + ' <> 1)'
    s = left + rng.choice([' ', '']) + op + rng.choice([' ', '']) + right
    if rng.random() < 0.15:
        cmp = rng.choice(['==', '!=', '<', '>'])
        s = '((' + s + ') ' + cmp + ' ' + rand_expr(rng, names, 0) + ')'
    return s


def rand_block(rng, names, depth, in_loop, budget, lines):
    count = rng.randrange(1, 6)
    for _ in range(count):
        if budget[0] <= 0:
            return
        budget[0] -= 1
        ind = '  ' * depth
        r = rng.random()
        if r < 0.35 or not names:
            name = rng.choice(['a', 'b', 'c', 'x', 'y_1', 'zz', '_t'])
            lines.append('%sset %s = %s' % (ind, name, rand_expr(rng, names, rng.randrange(0, 4))))
            if name not in names:
                names.append(name)
        elif r < 0.6:
            n = rng.randrange(1, 4)
            lines.append('%sout %s' % (ind, ', '.join(rand_expr(rng, names, rng.randrange(0, 4)) for _ in range(n))))
        elif r < 0.72 and depth < 4:
            lines.append('%sloop %d' % (ind, rng.randrange(0, 4)))
            rand_block(rng, names, depth + 1, True, budget, lines)
            lines.append(ind + 'end')
        elif r < 0.86 and depth < 4:
            lines.append('%swhen %s' % (ind, rand_expr(rng, names, 2)))
            rand_block(rng, names, depth + 1, in_loop, budget, lines)
            if rng.random() < 0.5:
                lines.append(ind + 'else')
                rand_block(rng, names, depth + 1, in_loop, budget, lines)
            lines.append(ind + 'end')
        elif r < 0.9 and in_loop:
            lines.append(ind + 'break')
        else:
            lines.append(ind + rng.choice(['', '; comment', '   ', '\t; x = 1/0']))


def rand_script(rng):
    lines = []
    names = []
    rand_block(rng, names, 0, False, [rng.randrange(8, 40)], lines)
    lines.append('out ' + ', '.join(names or ['0']))
    if rng.random() < 0.3:
        lines.append('out nope_undefined')
    return script(*lines)


def cases(rng):
    public = [
        ('example', EXAMPLE.encode(), A),
        ('parse_error', script('set a = 1', 'out a + 2', 'out a < 1 < 2', 'out )'), A),
        ('runtime_error', script('set n = 3', 'loop 5', '  out n, 12 / n', '  set n = n - 1', 'end'), A),
    ]
    hidden = [
        ('empty_file', b'', A),
        ('only_comments', script('; nothing', '   ', '\t;;', ''), A),
        ('no_final_newline', script('set a = 5', 'out a * a', final=False), A),
        ('crlf_and_tabs', b'set\ta\t=\t7\r\n\tout a,a\r\n', A),
        ('wraparound', script('out 4294967295 + 1, 0 - 1, 65536 * 65536, 65537 * 65537, -0, -1, - 4294967295',
                              'out 4294967295 * 4294967295, 7 / 2, 7 % 2, 0 / 5, 4294967295 / 1, 4294967295 % 10'), A),
        ('rotate', script('out 1 ~ 0, 1 ~ 1, 1 ~ 31, 1 ~ 32, 1 ~ 33, 2147483648 ~ 1, 4294967295 ~ 7',
                          'out 305419896 ~ 4, 305419896 ~ 28, 2 ~ 3 ~ 1, (2 ~ 3) ~ 1, -1 ~ 4, 2 ~ -1, 3 ~ 4294967295'), A),
        ('prefix_ops', script('out #0, #4294967295, #255, !0, !5, !!7, - -3, --3, -#-1, #-1, !-0, -!0, ##7',
                              'out -2 * 3, -(2 * 3), #3 ~ 1, # 3 ~ 1, !0 + 1, 2 - -2, 2--2'), A),
        ('precedence', script('out 1 + 2 * 3, (1 + 2) * 3, 10 - 2 - 3, 100 / 10 / 5, 2 * 3 % 4, 1 + 2 ~ 3, 5 <> 3 + 4',
                              'out 3 >< 9 <> 4, 3 >< (9 <> 4), 1 < 2 <> 7, 2 == 2 >< 5 == 5, 1 + 1 == 2',
                              'out 5 > 3, 3 > 5, 5 != 5, 4 != 5, 0 == 0, 0 < 0'), A),
        ('comparison_chain_error', script('out 1', 'out (1 < 2) < 3', 'out 1 == 1 != 0'), A),
        ('comparison_chain_error2', script('out 1 < 2 <> 3 > 1 < 5'), A),
        ('longest_match', script('out 3<>4, 3><4, 3< >4'), A),
        ('longest_match2', script('out 3<>4, 3><4', 'out 3 >= 4'), A),
        ('not_equal_token', script('set x = 3', 'out !x, x != 3', 'out !=x'), A),
        ('keyword_as_name', script('set a = 1', 'set end = 2'), A),
        ('keyword_in_expr', script('out 1', 'out loop'), A),
        ('keyword_prefix_names', script('set ends = 1', 'set loops = 2', 'set outx = 3', 'set _ = 4', 'set when_ = 5',
                                        'out ends + loops + outx + _ + when_'), A),
        ('number_too_big', script('out 4294967295', 'out 4294967296'), A),
        ('leading_zeros', script('out 007, 0000000000000000000000004294967295, 00'), A),
        ('number_then_word', script('out 1', 'out 12ab'), A),
        ('uppercase', script('set a = 1', 'out A'), A),
        ('bad_char', script('out 1', 'out 1 & 2'), A),
        ('bad_byte_in_comment', b'out 1\nout 2 ; caf\xc3\xa9\nout 3\n', A),
        ('nul_byte', b'out 1\nout\x002\n', A),
        ('line_1000', script('out 1', ('out ' + '+'.join(['1'] * 498)).ljust(1000)), A),
        ('line_1001', script('out 1', ('out ' + '+'.join(['1'] * 498)).ljust(1001)), A),
        ('long_comment_line', script('out 1', '; ' + 'x' * 1100), A),
        ('trailing_tokens', script('set a = 1', 'loop 2 3', 'end'), A),
        ('set_double_equals', script('set a == 1'), A),
        ('set_missing_expr', script('set a ='), A),
        ('out_trailing_comma', script('out 1,'), A),
        ('out_empty', script('out'), A),
        ('else_without_when', script('loop 2', 'else', 'end'), A),
        ('double_else', script('when 1', 'out 1', 'else', 'out 2', 'else', 'end'), A),
        ('stray_end', script('out 1', 'end', 'out 2'), A),
        ('unclosed_blocks', script('loop 1', '  when 1', '    out 1', '  end', '  loop 2', '  out 5'), A),
        ('break_outside_loop', script('when 1', '  break', 'end'), A),
        ('break_in_when_in_loop', script('set i = 0', 'loop 10', '  set i = i + 1', '  when i == 4', '    break', '  end',
                                         '  loop 3', '    when 1', '      break', '    end', '    out 99', '  end', 'end', 'out i'), A),
        ('nesting_16', script(*(['loop 1'] * 16 + ['out 16'] + ['end'] * 16)), A),
        ('nesting_17', script(*(['when 1'] * 8 + ['loop 1'] * 9 + ['out 17'] + ['end'] * 17)), A),
        ('parens_32', script('out ' + '(' * 32 + '5' + ')' * 32, 'out ' + '(1+' * 32 + '0' + ')' * 32), A),
        ('parens_33', script('out ' + '(' * 32 + '5' + ')' * 32, 'out ' + '(' * 33 + '5' + ')' * 33), A),
        ('parens_sequential', script('out ' + '+'.join(['(' * 30 + '1' + ')' * 30] * 3)), A),
        ('unbalanced_paren', script('out (1 + 2'), A),
        ('long_unary_chain', script('out ' + '-' * 990 + '5', 'out ' + '!' * 991 + '0'), A),
        ('undefined_var', script('set a = 1', 'out a', 'out a, b', 'out 3'), A),
        ('div_zero_in_loop', script('set i = 3', 'loop 10', '  out 100 / i', '  set i = i - 1', 'end'), A),
        ('mod_zero', script('out 5 % 1', 'out 5 % (2 - 2)'), A),
        ('runtime_error_in_when_header', script('out 1', 'when 1 / 0', 'out 2', 'end'), A),
        ('runtime_error_in_loop_header', script('out 1', 'loop zz', 'end'), A),
        ('parse_error_beats_runtime', script('out 1 / 0', 'out 2', 'out (', 'out 3'), A),
        ('parse_error_after_unclosed', script('loop 1', 'out 1', 'out 1 +'), A),
        ('no_short_circuit', script('out 0 * (1 / 0)'), A),
        ('loop_zero', script('loop 0', '  out 1 / 0', 'end', 'out 7'), A),
        ('loop_count_once', script('set n = 3', 'loop n', '  set n = n + 1', '  out n', 'end'), A),
        ('else_branch', script('set k = 0', 'loop 6', '  when k % 2', '    out k, 1', '  else', '    out k, 0', '  end',
                               '  set k = k + 1', 'end'), A),
        ('empty_bodies', script('loop 3', 'end', 'when 0', 'else', 'end', 'when 1', 'end', 'out 1'), A),
        ('global_vars', script('loop 2', '  set q = 5', 'end', 'out q', 'when 0', '  set never = 1', 'end', 'out never'), A),
        ('missing_file', b'', ['{input}.missing']),
        ('no_args', b'', []),
        ('two_args', script('out 1'), ['{input}', '{input}']),
    ]
    for k in range(12):
        hidden.append(('random%d' % k, rand_script(rng), A))
    perf = ('perf', PERF.encode(), A)
    return public, hidden, perf


PERF = '''; mixing loop
set h = 2166136261
set a = 1
set b = 0
set c = 7
set i = 0
loop 2500
  set j = 0
  loop 4000
    set h = (h ~ 5) * 16777619 + j
    set a = a + (h >< 65535) ~ j % 7
    when h % 3 == 0
      set b = b + #h
    else
      set c = c * 3 + h / 1024
    end
    when j > 3990
      break
    end
    set j = j + 1
  end
  set i = i + 1
  when i % 250 == 0
    out i, h, a, b, c
  end
end
out h, a, b, c, i <> j
'''
