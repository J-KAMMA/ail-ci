"""Cases for ticket_audit (see spec.md). cases(rng) -> (public, hidden, perf)."""

A = ['{input}']


def event_id(rng, base=None):
    d = [rng.randrange(10) for _ in range(5)] if base is None else [int(c) for c in '%05d' % base]
    d6 = (-(3 * (d[0] + d[2] + d[4]) + d[1] + d[3])) % 10
    return ''.join(map(str, d)) + str(d6)


def bad_event_id(rng):
    e = event_id(rng)
    return e[:5] + str((int(e[5]) + 1 + rng.randrange(9)) % 10)


def price_str(cents):
    return '%d.%02d' % (cents // 100, cents % 100)


class Log:
    """Builds a valid log and tracks what END must say."""

    def __init__(self, rng):
        self.rng = rng
        self.lines = ['TKT/1']
        self.venues = {}       # code -> capacity
        self.events = {}       # id -> [venue, cents, sold set]
        self.records = 0
        self.revenue = 0

    def add(self, line):
        self.lines.append(line)
        self.records += 1

    def venue(self, code=None, name=None, cap=None):
        rng = self.rng
        while code is None or code in self.venues:
            code = ''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(3))
        cap = cap if cap is not None else rng.randrange(1, 12)
        name = name or rng.choice(['Main Hall', 'The Dome', 'x', 'Club #9', 'Arena-North', 'Open Air Stage (B)'])
        self.venues[code] = cap
        self.add('V|%s|%s|%d' % (code, name, cap))
        return code

    def event(self, venue=None, eid=None, cents=None):
        rng = self.rng
        venue = venue or rng.choice(sorted(self.venues))
        while eid is None or eid in self.events:
            eid = event_id(rng)
        cents = cents if cents is not None else 5 * rng.randrange(0, 200000)
        date = '20%02d-%02d-%02d' % (rng.randrange(100), rng.randrange(1, 13), rng.randrange(1, 29))
        tm = '%02d:%02d' % (rng.randrange(24), rng.randrange(60))
        self.events[eid] = [venue, cents, set()]
        self.add('E|%s|%s|%s|%s|%s' % (eid, venue, date, tm, price_str(cents)))
        return eid

    def sell(self, eid=None, seat=None, buyer=None):
        rng = self.rng
        open_events = [e for e, ev in self.events.items() if len(ev[2]) < self.venues[ev[0]]]
        if eid is None:
            if not open_events:
                return False
            eid = rng.choice(open_events)
        ev = self.events[eid]
        while seat is None or seat in ev[2]:
            seat = rng.choice('ABCDEFGHIJ') + str(rng.randrange(1, 1000))
        buyer = buyer or rng.choice('abcxyz') + ''.join(rng.choice('abcdefghijklmnopqrstuvwxyz0123456789')
                                                      for _ in range(rng.randrange(3, 12)))
        ev[2].add(seat)
        self.revenue += ev[1]
        self.add('S|%s|%s|%s' % (eid, seat, buyer))
        return True

    def refund(self, eid=None, seat=None):
        rng = self.rng
        if eid is None:
            sold = [e for e, ev in self.events.items() if ev[2]]
            if not sold:
                return False
            eid = rng.choice(sold)
        ev = self.events[eid]
        seat = seat or rng.choice(sorted(ev[2]))
        ev[2].remove(seat)
        self.revenue -= ev[1]
        self.add('R|%s|%s' % (eid, seat))
        return True

    def end(self, count=None, cents=None):
        self.lines.append('END|%d|%d' % (self.records if count is None else count,
                                         self.revenue if cents is None else cents))
        return self

    def data(self, final=True):
        return ('\n'.join(self.lines) + ('\n' if final else '')).encode()


def random_log(rng, nv, ne, nops, refund=0.15):
    log = Log(rng)
    for _ in range(nv):
        log.venue()
    for _ in range(ne):
        log.event()
    for _ in range(nops):
        if rng.random() < refund:
            log.refund() or log.sell()
        else:
            log.sell() or log.refund()
    return log


def base(rng):
    log = Log(rng)
    log.venue('ABC', 'Main Hall', 3)
    log.venue('XYZ', 'Club #9', 100000)
    log.event('ABC', '123457', 2550)
    log.event('XYZ', '000000', 5)
    log.sell('123457', 'A1', 'alice')
    log.sell('123457', 'B12', 'bob1')
    log.sell('000000', 'Z999', 'carol')
    log.refund('123457', 'A1')
    log.sell('123457', 'A1', 'dave')
    return log


def with_line(rng, line, at=None):
    """The base log with one extra record inserted before END (END totals unchanged: the error comes first)."""
    log = base(rng)
    log.lines.insert(at if at is not None else len(log.lines), line)
    return log.end().data()


def cases(rng):
    good = base(rng).end().data()
    public = [
        ('valid', good, A),
        ('capacity_error', with_line(rng, 'S|123457|C3|erin\nS|123457|D4|fred'), A),
        ('bad_date', with_line(rng, 'E|111119|ABC|2023-02-29|10:00|1.00'), A),
    ]
    assert event_id(rng, 12345) == '123457'
    hidden = [
        ('valid_no_final_newline', base(rng).end().data(final=False), A),
        ('only_header_and_end', b'TKT/1\nEND|0|0\n', A),
        ('empty_file', b'', A),
        ('header_wrong', b'TKT/2\nEND|0|0\n', A),
        ('header_crlf', b'TKT/1\r\nEND|0|0\r\n', A),
        ('header_only', b'TKT/1\n', A),
        ('header_only_no_newline', b'TKT/1', A),
        ('missing_end', base(rng).data(), A),
        ('line_after_end', base(rng).end().data() + b'V|QQQ|late|5\n', A),
        ('empty_line_after_end', base(rng).end().data() + b'\n', A),
        ('end_count_wrong', base(rng).end(count=6).data(), A),
        ('end_cents_wrong', base(rng).end(cents=1).data(), A),
        ('end_leading_zero', base(rng).end().data().replace(b'END|9|', b'END|09|'), A),
        ('end_bad_syntax', base(rng).end().data().replace(b'END|9|', b'END|9x|'), A),
        ('end_extra_field', base(rng).end().data().replace(b'END|9|', b'END|9|9|'), A),
        ('empty_record_line', with_line(rng, '', at=3), A),
        ('unknown_type', with_line(rng, 'X|1|2'), A),
        ('lowercase_type', with_line(rng, 'v|QQQ|Hall|5'), A),
        ('too_few_fields', with_line(rng, 'V|QQQ|Hall'), A),
        ('too_many_fields', with_line(rng, 'S|123457|C3|erin|x'), A),
        ('crlf_record', with_line(rng, 'V|QQQ|Hall|5\r'), A),
        ('tab_in_name', with_line(rng, 'V|QQQ|Hall\tB|5'), A),
        ('name_leading_space', with_line(rng, 'V|QQQ| Hall|5'), A),
        ('name_trailing_space', with_line(rng, 'V|QQQ|Hall |5'), A),
        ('name_inner_spaces_ok', with_line(rng, 'V|QQQ|A  B ~ {}|5'), A),
        ('name_40', with_line(rng, 'V|QQQ|' + 'n' * 40 + '|5'), A),
        ('name_41', with_line(rng, 'V|QQQ|' + 'n' * 41 + '|5'), A),
        ('name_non_ascii', with_line(rng, 'V|QQQ|Café|5'), A),
        ('code_lowercase', with_line(rng, 'V|QqQ|Hall|5'), A),
        ('code_4_letters', with_line(rng, 'V|QQQQ|Hall|5'), A),
        ('capacity_zero', with_line(rng, 'V|QQQ|Hall|0'), A),
        ('capacity_leading_zero', with_line(rng, 'V|QQQ|Hall|05'), A),
        ('capacity_too_big', with_line(rng, 'V|QQQ|Hall|100001'), A),
        ('capacity_max', with_line(rng, 'V|QQQ|Hall|100000'), A),
        ('capacity_7_digits', with_line(rng, 'V|QQQ|Hall|1000000'), A),
        ('venue_duplicate', with_line(rng, 'V|ABC|Other|5'), A),
        ('event_check_digit', with_line(rng, 'E|123458|ABC|2024-01-01|10:00|1.00'), A),
        ('event_5_digits', with_line(rng, 'E|12345|ABC|2024-01-01|10:00|1.00'), A),
        ('event_unknown_venue', with_line(rng, 'E|111119|QQQ|2024-01-01|10:00|1.00'), A),
        ('event_duplicate', with_line(rng, 'E|123457|XYZ|2024-01-01|10:00|1.00'), A),
        ('event_unknown_venue_and_duplicate', with_line(rng, 'E|123457|QQQ|2024-01-01|10:00|1.00'), A),
        ('syntax_before_value', with_line(rng, 'E|123458|ABC|2024-1-01|10:00|1.00'), A),
        ('value_before_reference', with_line(rng, 'E|123458|QQQ|2024-01-01|10:00|1.00'), A),
        ('leap_day_ok', with_line(rng, 'E|111119|ABC|2024-02-29|00:00|0.00'), A),
        ('leap_2000_ok', with_line(rng, 'E|111119|ABC|2000-02-29|23:59|9999.95'), A),
        ('year_2100', with_line(rng, 'E|111119|ABC|2100-01-01|10:00|1.00'), A),
        ('year_1999', with_line(rng, 'E|111119|ABC|1999-12-31|10:00|1.00'), A),
        ('month_13', with_line(rng, 'E|111119|ABC|2024-13-01|10:00|1.00'), A),
        ('day_31_april', with_line(rng, 'E|111119|ABC|2024-04-31|10:00|1.00'), A),
        ('day_zero', with_line(rng, 'E|111119|ABC|2024-05-00|10:00|1.00'), A),
        ('hour_24', with_line(rng, 'E|111119|ABC|2024-05-01|24:00|1.00'), A),
        ('minute_60', with_line(rng, 'E|111119|ABC|2024-05-01|23:60|1.00'), A),
        ('time_one_digit', with_line(rng, 'E|111119|ABC|2024-05-01|9:00|1.00'), A),
        ('price_not_multiple_5', with_line(rng, 'E|111119|ABC|2024-05-01|09:00|1.03'), A),
        ('price_leading_zero', with_line(rng, 'E|111119|ABC|2024-05-01|09:00|01.00'), A),
        ('price_zero_whole_ok', with_line(rng, 'E|111119|ABC|2024-05-01|09:00|0.95'), A),
        ('price_one_decimal', with_line(rng, 'E|111119|ABC|2024-05-01|09:00|1.5'), A),
        ('price_five_digits', with_line(rng, 'E|111119|ABC|2024-05-01|09:00|10000.00'), A),
        ('seat_leading_zero', with_line(rng, 'S|000000|A01|zed1'), A),
        ('seat_zero', with_line(rng, 'S|000000|A0|zed1'), A),
        ('seat_4_digits', with_line(rng, 'S|000000|A1000|zed1'), A),
        ('seat_lowercase', with_line(rng, 'S|000000|a1|zed1'), A),
        ('buyer_short', with_line(rng, 'S|000000|A1|abc'), A),
        ('buyer_long', with_line(rng, 'S|000000|A1|abcdefghijklm'), A),
        ('buyer_digit_first', with_line(rng, 'S|000000|A1|1abc'), A),
        ('buyer_upper', with_line(rng, 'S|000000|A1|Abcd'), A),
        ('sale_unknown_event', with_line(rng, 'S|111119|A1|zed1'), A),
        ('sale_bad_check_digit', with_line(rng, 'S|111112|A1|zed1'), A),
        ('sale_duplicate_seat', with_line(rng, 'S|000000|Z999|zed1'), A),
        ('sale_duplicate_beats_capacity', with_line(rng, 'S|123457|C3|erin\nS|123457|A1|zed1'), A),
        ('refund_unsold_seat', with_line(rng, 'R|000000|Z998'), A),
        ('refund_unknown_event', with_line(rng, 'R|111119|A1'), A),
        ('refund_twice', with_line(rng, 'R|000000|Z999\nR|000000|Z999'), A),
        ('missing_file', b'', ['{input}.missing']),
        ('no_args', b'', []),
        ('two_args', good, ['{input}', '{input}']),
    ]
    log = base(rng)
    log.refund('123457', 'B12')
    log.sell('123457', 'C3', 'resale')
    log.sell('123457', 'B12', 'again')
    hidden.append(('resell_after_refund', log.end().data(), A))
    log = Log(rng)
    for code in ('MMM', 'AAA', 'ZZZ', 'BBB'):
        log.venue(code, 'v ' + code, 4)
    for k, v in enumerate(('MMM', 'AAA', 'AAA', 'ZZZ', 'MMM')):
        log.event(v, event_id(rng, 10000 * (k + 1)), 100 * (k + 1))
    for e in sorted(log.events):
        for s in range(3 if e < '300000' else 1):
            log.sell(e, 'A%d' % (s + 1), 'buyer')
    hidden.append(('top_ties_and_unused_venue', log.end().data(), A))
    for k in range(6):
        hidden.append(('random%d' % k, random_log(rng, rng.randrange(1, 6), rng.randrange(1, 10), rng.randrange(0, 80)).end().data(), A))
    for k in range(4):
        log = random_log(rng, 3, 6, 60)
        lines = log.end().lines
        i = rng.randrange(1, len(lines))
        line = list(lines[i])
        j = rng.randrange(len(line))
        line[j] = rng.choice('0123456789|AZaz.:- ')
        lines[i] = ''.join(line)
        hidden.append(('mutated%d' % k, ('\n'.join(lines) + '\n').encode(), A))
    perf = ('perf', perf_log(rng), A)
    return public, hidden, perf


def perf_log(rng, nv=800, ne=60000, nsales=2600000, nref=200000):
    lines = ['TKT/1']
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    codes = rng.sample([a + b + c for a in letters for b in letters for c in letters], nv)
    cap = {}
    for c in codes:
        cap[c] = rng.randrange(60, 2000)
        lines.append('V|%s|Venue %s hall|%d' % (c, c, cap[c]))
    eids = rng.sample(range(100000), ne)
    events = []
    price = {}
    for base in eids:
        e = event_id(rng, base)
        v = rng.choice(codes)
        cents = 5 * rng.randrange(100, 40000)
        price[e] = cents
        events.append((e, v))
        lines.append('E|%s|%s|20%02d-%02d-%02d|%02d:%02d|%s' % (e, v, rng.randrange(100), rng.randrange(1, 13), rng.randrange(1, 29),
                                                               rng.randrange(24), rng.randrange(60), price_str(cents)))
    sold = {e: [] for e, _ in events}
    seatsets = {e: set() for e, _ in events}
    vcap = dict(events)
    revenue = 0
    nrec = nv + ne
    rand = rng.random
    choice = rng.choice
    randrange = rng.randrange
    buyers = ['b%06d' % i for i in range(5000)]
    refund_p = nref / (nsales + nref)
    for _ in range(nsales + nref):
        e, v = choice(events)
        if rand() < refund_p and sold[e]:
            lst = sold[e]
            k = randrange(len(lst))
            seat = lst[k]
            lst[k] = lst[-1]
            lst.pop()
            seatsets[e].discard(seat)
            revenue -= price[e]
            lines.append('R|%s|%s' % (e, seat))
        else:
            if len(sold[e]) >= cap[v]:
                continue
            while True:
                seat = letters[randrange(26)] + str(randrange(1, 1000))
                if seat not in seatsets[e]:
                    break
            sold[e].append(seat)
            seatsets[e].add(seat)
            revenue += price[e]
            lines.append('S|%s|%s|%s' % (e, seat, choice(buyers)))
        nrec += 1
    lines.append('END|%d|%d' % (nrec, revenue))
    return ('\n'.join(lines) + '\n').encode()
