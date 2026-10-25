class Box:
    def __init__(self, v):
        self.v = v

def hi(v, spec):
    return format(v, spec)

def pcthi(v, spec):
    return ('%' + spec) % v

def show(tag, fn):
    try:
        print(tag, repr(fn()))
    except Exception as e:
        print(tag, type(e).__name__, e)

big = 10 ** 308
box = Box(big)
items = [big]
d = {'k': big}
print('hi_pos_e', format(big, '.400e'))
print('hi_neg_E', format(-big, '.400E'))
print('hi_pos_g', format(big, '.400g'))
print('hi_pos_f', format(big, '.400f'))
print('hi_pos_pct', format(big, '.400%'))
print('hi_two1023_e', format(2 ** 1023, '.400e'))
print('hi_pct_e', '%.400e' % big)
print('hi_pct_neg_f', '%.400f' % (-big))
for tag, v in (('arg', big), ('list', items[0]), ('dict', d['k']), ('attr', box.v)):
    s = hi(v, '.400e')
    print('hi_src', tag, len(s), s[:20], s[-20:])
    s = pcthi(v, '.400f')
    print('hi_pctsrc', tag, len(s), s[:20], s[-20:])
show('hi_ten400_fmt', lambda: format(10 ** 400, '.400e'))
show('hi_ten400_pct', lambda: '%.400e' % (10 ** 400))

bigc = 10 ** 400
boxc = Box(bigc)
itemsc = [bigc]
dc = {'k': bigc}
for tag, v in (('big', bigc), ('neg', -bigc), ('list', itemsc[0]), ('dict', dc['k']), ('attr', boxc.v)):
    show('char_fmt_' + tag, lambda v=v: format(v, 'c'))
    show('char_pct_' + tag, lambda v=v: '%c' % v)
for tag, v in (('two63', 2 ** 63), ('two63m1', 2 ** 63 - 1), ('ten18', 10 ** 18),
               ('c65', 65), ('overcp', 0x110000), ('neg1', -1)):
    show('char_fmt_' + tag, lambda v=v: format(v, 'c'))
    show('char_pct_' + tag, lambda v=v: '%c' % v)
for spec in ('+c', '#c', '.2c', '05c', '>c'):
    show('char_bigspec_' + spec, lambda spec=spec: format(bigc, spec))
    show('char_smallspec_' + spec, lambda spec=spec: format(65, spec))
