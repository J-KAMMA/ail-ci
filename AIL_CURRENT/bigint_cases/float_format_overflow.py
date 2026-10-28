class Box:
    def __init__(self, v):
        self.v = v

def pct_f(x):
    return '%f' % x

def pct_e(x):
    return '%e' % x

def pct_g(x):
    return '%g' % x

def pct_F(x):
    return '%F' % x

def shown(tag, fn):
    try:
        print(tag, fn())
    except OverflowError as e:
        print(tag, 'OverflowError', e)

big = 10 ** 400
box = Box(big)
items = [big]
d = {'k': big}

for tag, v in (('arg', big), ('neg', -big), ('list', items[0]), ('dict', d['k']), ('attr', box.v)):
    shown(tag + '_pctf', lambda: pct_f(v))
    shown(tag + '_pcte', lambda: pct_e(v))
    shown(tag + '_pctg', lambda: pct_g(v))
    shown(tag + '_pctF', lambda: pct_F(v))
    shown(tag + '_fmtf', lambda: format(v, '.2f'))
    shown(tag + '_fmtf_noprec', lambda: format(v, 'f'))
    shown(tag + '_fmtF', lambda: format(v, 'F'))
    shown(tag + '_fmte', lambda: format(v, 'e'))
    shown(tag + '_fmtg', lambda: format(v, 'g'))
    shown(tag + '_fmtpercent', lambda: format(v, '%'))
    shown(tag + '_fstrf', lambda: f'{v:f}')
    shown(tag + '_fstrF', lambda: f'{v:F}')
    shown(tag + '_fstre', lambda: f'{v:e}')
    shown(tag + '_fstrpercent', lambda: f'{v:%}')

shown('two1024', lambda: format(2 ** 1024, '.2f'))
shown('neg_two1024', lambda: '%f' % (-(2 ** 1024)))
shown('boundary_overflow', lambda: '%f' % (2 ** 1024 - 2 ** 970))
shown('boundary_neg_overflow', lambda: '%e' % (-(2 ** 1024 - 2 ** 970)))
shown('ten309_g', lambda: '%g' % (10 ** 309))
shown('pct_upper_e', lambda: '%E' % big)
shown('pct_upper_g', lambda: '%G' % big)
shown('pct_percent', lambda: '%f%%' % big)
shown('fmt_percent', lambda: format(big, '%'))
shown('alias_fmtf', lambda: format((lambda y: y)(big), '.2f'))
shown('two1024_m_971_f', lambda: format(2 ** 1024 - 2 ** 971, '.2f'))
shown('two1024_m_972_g', lambda: '%g' % (2 ** 1024 - 2 ** 972))
shown('dblmax_int_p1_e', lambda: '%e' % (int(1.7976931348623157e308) + 1))
shown('two1023_f', lambda: '%f' % (2 ** 1023))
shown('two1023_e', lambda: '%e' % (2 ** 1023))
shown('two1023_g', lambda: '%g' % (2 ** 1023))
shown('ten100_f', lambda: '%.2f' % (10 ** 100))
shown('ten100_fmt', lambda: format(10 ** 100, '.2f'))
shown('ten100_group', lambda: format(10 ** 100, ',.2f')[:50])
shown('ten100_sign', lambda: format(-(10 ** 100), ' .2f')[:50])
shown('small_int', lambda: '%f' % 12345)
shown('float_val', lambda: '%f' % 1e300)

shown('pct_tuple_big', lambda: '%f' % (big,))
shown('pct_map_big', lambda: '%(x)f' % {'x': big})
shown('pct_width_big', lambda: '%50.2f' % big)
shown('pct_left_big', lambda: '%-50e' % big)
shown('pct_star_big', lambda: '%*.*f' % (20, 2, big))
shown('fmt_n_big', lambda: format(big, 'n'))
shown('fmt_empty_big', lambda: format(big, ''))
shown('float_big', lambda: float(big))
shown('float_neg_big', lambda: float(-big))
shown('float_two1024', lambda: float(2 ** 1024))
shown('float_boundary_big', lambda: float(2 ** 1024 - 2 ** 970))
shown('float_two1023', lambda: float(2 ** 1023))
