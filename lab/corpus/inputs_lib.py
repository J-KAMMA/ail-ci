"""Seeded input generators for corpus tasks. Each takes (rng, k) where k in 0..2 is the input index
(0 small, 1 medium, 2 larger) and returns the stdin text. Needs Python 3.12 (nested f-string quotes)."""
import json

WORDS = ["apple", "banana", "cherry", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet",
         "kilo", "lima", "mike", "november", "oscar", "papa", "quebec", "romeo", "sierra", "tango",
         "uniform", "victor", "whiskey", "xray", "yankee", "zulu"]
UWORDS = ["café", "naïve", "über", "straße", "日本語", "東京", "ångström",
          "да", "мир", "αβγ", "señor", "élève", "Ńódź", "\U0001f600smile"]
NAMES = ["alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi", "ivan", "judy", "mallory", "niaj"]
SIZE = [(4, 8), (10, 25), (30, 80)]


def n_of(rng, k, scale=1):
    lo, hi = SIZE[k]
    return rng.randint(lo, hi) * scale


def nums(rng, k, lo=-50, hi=50, count_line=True):
    n = n_of(rng, k)
    xs = [rng.randint(lo, hi) for _ in range(n)]
    return (f"{n}\n" if count_line else "") + " ".join(map(str, xs)) + "\n"


def nums_nocount(rng, k):
    return nums(rng, k, -50, 50, False)


def pos_nums(rng, k):
    return nums(rng, k, 1, 100)


def one_int(rng, k, lo=1, hi=None):
    hi = hi or [30, 200, 5000][k]
    return f"{rng.randint(lo, hi)}\n"


def small_int(rng, k):
    return f"{rng.randint(1, [10, 30, 60][k])}\n"


def two_ints(rng, k):
    hi = [20, 500, 100000][k]
    return f"{rng.randint(1, hi)} {rng.randint(1, hi)}\n"


def words_line(rng, k, uni=False):
    pool = WORDS + (UWORDS if uni else [])
    return " ".join(rng.choice(pool) for _ in range(n_of(rng, k))) + "\n"


def words_line_uni(rng, k):
    return words_line(rng, k, True)


def text_lines(rng, k, uni=False):
    pool = WORDS + (UWORDS if uni else [])
    nl = [(2, 4), (4, 8), (8, 20)][k]
    lines = []
    for _ in range(rng.randint(*nl)):
        w = [rng.choice(pool) for _ in range(rng.randint(0, 9))]
        if rng.random() < 0.3 and w:
            w[rng.randrange(len(w))] += rng.choice([",", ".", "!", ";"])
        lines.append(" ".join(w).capitalize() if rng.random() < 0.4 else " ".join(w))
    return "\n".join(lines) + "\n"


def text_uni(rng, k):
    return text_lines(rng, k, True)


def one_word(rng, k, uni=False):
    pool = WORDS + (UWORDS if uni else [])
    return "".join(rng.choice(pool) for _ in range(rng.randint(1, 1 + 2 * k))) + "\n"


def one_word_uni(rng, k):
    return one_word(rng, k, True)


def strings_n(rng, k, uni=False):
    n = n_of(rng, k)
    pool = WORDS + (UWORDS if uni else [])
    return f"{n}\n" + "\n".join(rng.choice(pool) for _ in range(n)) + "\n"


def strings_n_uni(rng, k):
    return strings_n(rng, k, True)


def palin_strings(rng, k):
    n = n_of(rng, k)
    out = []
    for _ in range(n):
        h = "".join(rng.choice("abcd") for _ in range(rng.randint(1, 5)))
        s = h + rng.choice(["", "x"]) + h[::-1] if rng.random() < 0.5 else h + "".join(rng.choice("abcd") for _ in range(3))
        out.append(s)
    return f"{n}\n" + "\n".join(out) + "\n"


def name_scores(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + "\n".join(f"{rng.choice(NAMES)} {rng.randint(0, 100)}" for _ in range(n)) + "\n"


def name_score_float(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + "\n".join(f"{rng.choice(NAMES)} {rng.randint(0, 10000) / 100:.2f}" for _ in range(n)) + "\n"


def csv_table(rng, k):
    n = n_of(rng, k)
    depts = ["eng", "ops", "hr", "sales"]
    rows = ["name,dept,salary,age"]
    for _ in range(n):
        rows.append(f"{rng.choice(NAMES)},{rng.choice(depts)},{rng.randint(30, 200) * 1000},{rng.randint(20, 65)}")
    return "\n".join(rows) + "\n"


def grid(rng, k, chars=".#", p=0.25, start_end=False):
    h = [(3, 5), (5, 9), (10, 20)][k]
    h, w = rng.randint(*h), rng.randint(*h)
    g = [[chars[1] if rng.random() < p else chars[0] for _ in range(w)] for _ in range(h)]
    if start_end:
        g[0][0] = "S"
        g[h - 1][w - 1] = "E"
    return f"{h} {w}\n" + "\n".join("".join(r) for r in g) + "\n"


def grid_se(rng, k):
    return grid(rng, k, ".#", 0.25, True)


def grid_life(rng, k):
    return grid(rng, k, ".#", 0.4)


def grid_digits(rng, k):
    h = [(3, 5), (5, 9), (10, 20)][k]
    h, w = rng.randint(*h), rng.randint(*h)
    return f"{h} {w}\n" + "\n".join("".join(str(rng.randint(1, 9)) for _ in range(w)) for _ in range(h)) + "\n"


def int_matrix(rng, k):
    h = [(2, 4), (4, 7), (8, 14)][k]
    r, c = rng.randint(*h), rng.randint(*h)
    return f"{r} {c}\n" + "\n".join(" ".join(str(rng.randint(-9, 9)) for _ in range(c)) for _ in range(r)) + "\n"


def square_matrix(rng, k):
    n = [(2, 4), (4, 6), (7, 10)][k]
    n = rng.randint(*n)
    return f"{n}\n" + "\n".join(" ".join(str(rng.randint(-5, 9)) for _ in range(n)) for _ in range(n)) + "\n"


def edges(rng, k, weighted=False, directed=False, connected=True):
    n = [(4, 7), (8, 15), (20, 40)][k]
    n = rng.randint(*n)
    es = set()
    if connected:
        for v in range(1, n):
            es.add((rng.randrange(v), v))
    for _ in range(rng.randint(0, n)):
        a, b = rng.randrange(n), rng.randrange(n)
        if a != b and (a, b) not in es and (directed or (b, a) not in es):
            es.add((a, b))
    es = sorted(es)
    rng.shuffle(es)
    lines = [f"{n} {len(es)}"]
    for a, b in es:
        lines.append(f"{a} {b} {rng.randint(1, 20)}" if weighted else f"{a} {b}")
    return "\n".join(lines) + "\n"


def edges_plain(rng, k): return edges(rng, k)
def edges_w(rng, k): return edges(rng, k, True)
def edges_d(rng, k): return edges(rng, k, False, True)
def edges_dw(rng, k): return edges(rng, k, True, True)
def edges_disc(rng, k): return edges(rng, k, False, False, False)


def dag(rng, k):
    n = [(4, 7), (8, 15), (20, 40)][k]
    n = rng.randint(*n)
    es = set()
    for _ in range(rng.randint(n - 1, 2 * n)):
        a, b = sorted(rng.sample(range(n), 2))
        es.add((a, b))
    perm = list(range(n))
    rng.shuffle(perm)
    es = sorted((perm[a], perm[b]) for a, b in es)
    return f"{n} {len(es)}\n" + "\n".join(f"{a} {b}" for a, b in es) + "\n"


def intervals(rng, k):
    n = n_of(rng, k)
    out = []
    for _ in range(n):
        a = rng.randint(0, 50 + 100 * k)
        out.append(f"{a} {a + rng.randint(1, 15)}")
    return f"{n}\n" + "\n".join(out) + "\n"


def knap(rng, k):
    n = [(3, 6), (8, 15), (20, 40)][k]
    n = rng.randint(*n)
    cap = rng.randint(10, 30 + 100 * k)
    return f"{n} {cap}\n" + "\n".join(f"{rng.randint(1, 20)} {rng.randint(1, 50)}" for _ in range(n)) + "\n"


def two_strings(rng, k):
    L = [(3, 7), (8, 20), (30, 60)][k]
    return "".join(rng.choice("abc") for _ in range(rng.randint(*L))) + "\n" + "".join(rng.choice("abc") for _ in range(rng.randint(*L))) + "\n"


def coins(rng, k):
    c = sorted(rng.sample([1, 2, 3, 5, 7, 10, 25, 50], rng.randint(2, 4)))
    return f"{len(c)}\n{' '.join(map(str, c))}\n{rng.randint(1, [30, 200, 1000][k])}\n"


def parens(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + "\n".join("".join(rng.choice("()[]{}") for _ in range(rng.randint(0, 12))) for _ in range(n)) + "\n"


def balanced_ish(rng, k):
    out = []
    for _ in range(n_of(rng, k)):
        s = ""
        st = []
        for _ in range(rng.randint(0, 8)):
            if st and rng.random() < 0.5:
                s += st.pop()
            else:
                o = rng.choice("([{")
                s += o
                st.append({"(": ")", "[": "]", "{": "}"}[o])
        s += "".join(reversed(st))
        if rng.random() < 0.3 and s:
            i = rng.randrange(len(s))
            s = s[:i] + rng.choice(")]}") + s[i + 1:]
        out.append(s)
    return f"{len(out)}\n" + "\n".join(out) + "\n"


def expr_lines(rng, k):
    out = []
    for _ in range(n_of(rng, k) // 2 + 1):
        t = [str(rng.randint(0, 20))]
        for _ in range(rng.randint(1, 4)):
            t.append(rng.choice("+-*/"))
            t.append(str(rng.randint(1, 20)))
        e = " ".join(t)
        if rng.random() < 0.3:
            e = "(" + e + ") * " + str(rng.randint(1, 5))
        out.append(e)
    return "\n".join(out) + "\n"


def commands(rng, k):
    out = []
    for _ in range(n_of(rng, k) * 2):
        c = rng.choice(["push", "push", "pop", "peek", "size"])
        out.append(f"{c} {rng.randint(1, 99)}" if c == "push" else c)
    return "\n".join(out) + "\n"


def kv_commands(rng, k):
    out = []
    for _ in range(n_of(rng, k) * 2):
        c = rng.choice(["set", "set", "get", "del", "incr", "count"])
        key = rng.choice(["a", "b", "c", "d", "e"])
        out.append(f"{c} {key} {rng.randint(1, 9)}" if c in ("set", "incr") else (f"{c} {key}" if c != "count" else "count"))
    return "\n".join(out) + "\n"


def json_records(rng, k):
    n = n_of(rng, k) // 2 + 1
    recs = []
    for i in range(n):
        r = {"id": i, "name": rng.choice(NAMES + UWORDS[:4]), "tags": rng.sample(WORDS[:8], rng.randint(0, 3)),
             "score": round(rng.random() * 100, 2), "active": rng.random() < 0.5}
        if rng.random() < 0.4:
            r["meta"] = {"level": rng.randint(1, 5), "note": None if rng.random() < 0.5 else 'x"y\\z'}
        recs.append(r)
    return json.dumps(recs, ensure_ascii=rng.random() < 0.5) + "\n"


def json_nested(rng, k):
    def mk(d):
        if d == 0 or rng.random() < 0.25:
            return rng.choice([rng.randint(-5, 5), rng.random() < 0.5, None, rng.choice(WORDS), round(rng.random(), 3)])
        if rng.random() < 0.5:
            return [mk(d - 1) for _ in range(rng.randint(0, 3))]
        return {rng.choice(WORDS[:6]): mk(d - 1) for _ in range(rng.randint(0, 3))}
    return json.dumps(mk(2 + k)) + "\n"


def log_lines(rng, k):
    lv = ["INFO", "WARN", "ERROR", "DEBUG"]
    out = []
    for _ in range(n_of(rng, k)):
        out.append(f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d} [{rng.choice(lv)}] {rng.choice(WORDS)} {rng.choice(WORDS)} code={rng.randint(100, 599)}")
    return "\n".join(out) + "\n"


def emails_text(rng, k):
    out = []
    for _ in range(n_of(rng, k) // 2 + 1):
        parts = [rng.choice(WORDS) for _ in range(rng.randint(2, 6))]
        if rng.random() < 0.7:
            parts.insert(rng.randrange(len(parts)), f"{rng.choice(NAMES)}.{rng.choice(NAMES)}@{rng.choice(WORDS)}.{rng.choice(['com', 'org', 'co.uk'])}")
        if rng.random() < 0.4:
            parts.insert(rng.randrange(len(parts)), f"{rng.randint(100, 999)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}")
        out.append(" ".join(parts))
    return "\n".join(out) + "\n"


def dates(rng, k):
    return "\n".join(f"{rng.randint(1900, 2100)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}" for _ in range(n_of(rng, k))) + "\n"


def times(rng, k):
    return "\n".join(f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}" for _ in range(n_of(rng, k))) + "\n"


def floats(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + " ".join(f"{rng.uniform(-100, 100):.3f}" for _ in range(n)) + "\n"


def big_ints(rng, k):
    n = rng.randint(2, 6)
    return f"{n}\n" + " ".join(str(rng.randint(1, 10 ** rng.randint(1, 12))) for _ in range(n)) + "\n"


def points(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + "\n".join(f"{rng.randint(-20, 20)} {rng.randint(-20, 20)}" for _ in range(n)) + "\n"


def bank_txns(rng, k):
    out = []
    for _ in range(n_of(rng, k) * 2):
        out.append(rng.choice(["deposit", "withdraw", "balance"]) + " " + rng.choice(["acc1", "acc2", "acc3"]) + " " + str(rng.randint(1, 500)))
    return "\n".join(out) + "\n"


def robot(rng, k):
    return "".join(rng.choice("FFFLRB") for _ in range([10, 40, 200][k])) + "\n"


def tokens_mixed(rng, k):
    out = []
    for _ in range(n_of(rng, k)):
        out.append(rng.choice([str(rng.randint(-99, 99)), "abc", "3.5", "", "0x1f", " 7 ", "1e3", "-", "12a", "٣"]))
    return "\n".join(out) + "\n"


def ints_and_queries(rng, k):
    n = n_of(rng, k)
    xs = [rng.randint(1, 100) for _ in range(n)]
    q = rng.randint(3, 3 + 6 * k)
    qs = []
    for _ in range(q):
        a = rng.randrange(n)
        b = rng.randrange(a, n)
        qs.append(f"{a} {b}")
    return f"{n} {q}\n" + " ".join(map(str, xs)) + "\n" + "\n".join(qs) + "\n"


def sorted_nums_target(rng, k):
    n = n_of(rng, k)
    xs = sorted(rng.randint(1, 200) for _ in range(n))
    return f"{n}\n" + " ".join(map(str, xs)) + "\n" + str(rng.choice(xs) + rng.choice([0, 0, 1])) + "\n"


def nums_target(rng, k):
    n = n_of(rng, k)
    xs = [rng.randint(-20, 40) for _ in range(n)]
    return f"{n} {rng.randint(0, 40)}\n" + " ".join(map(str, xs)) + "\n"


def student_records(rng, k):
    n = n_of(rng, k)
    return f"{n}\n" + "\n".join(f"{rng.choice(NAMES)} {rng.choice('ABC')} {rng.randint(15, 25)} {rng.randint(50, 100)}" for _ in range(n)) + "\n"


def inventory(rng, k):
    out = []
    for _ in range(n_of(rng, k) * 2):
        c = rng.choice(["add", "add", "remove", "report"])
        item = rng.choice(["bolt", "nut", "gear", "cog", "pin"])
        out.append(f"{c} {item} {rng.randint(1, 20)}" if c != "report" else "report")
    return "\n".join(out) + "\n"


def tasks_deps(rng, k):
    n = n_of(rng, k) // 2 + 3
    out = [str(n)]
    for i in range(n):
        deps = rng.sample(range(i), min(i, rng.randint(0, 2))) if i else []
        out.append(f"t{i} {rng.randint(1, 9)} " + " ".join(f"t{d}" for d in deps))
    return "\n".join(out).rstrip() + "\n"


def schedule_queue(rng, k):
    n = n_of(rng, k)
    return f"{n} {rng.randint(2, 5)}\n" + "\n".join(f"p{i} {rng.randint(1, 12)}" for i in range(n)) + "\n"


def tri_sides(rng, k):
    return "\n".join(f"{rng.randint(1, 15)} {rng.randint(1, 15)} {rng.randint(1, 15)}" for _ in range(n_of(rng, k))) + "\n"


def word_pairs(rng, k):
    out = []
    for _ in range(n_of(rng, k)):
        w = rng.choice(WORDS)
        v = "".join(rng.sample(w, len(w))) if rng.random() < 0.5 else rng.choice(WORDS)
        out.append(f"{w} {v}")
    return "\n".join(out) + "\n"


def rle_input(rng, k):
    return "\n".join("".join(c * rng.randint(1, 5) for c in rng.choices("abcxyz", k=rng.randint(1, 8))) for _ in range(n_of(rng, k) // 2 + 1)) + "\n"


def int_lines_4000(rng, k):
    return "\n".join(str(rng.randint(1, 3999)) for _ in range(n_of(rng, k))) + "\n"


def bin_strs(rng, k):
    return "\n".join("".join(rng.choice("01") for _ in range(rng.randint(1, 20))) for _ in range(n_of(rng, k))) + "\n"


def hex_lines(rng, k):
    return "\n".join(f"{rng.randint(0, 2 ** 32):x}" for _ in range(n_of(rng, k))) + "\n"


def matrix_pow(rng, k):
    n = rng.randint(2, 4 + 2 * k)
    return f"{n}\n" + "\n".join(" ".join(str(rng.randint(-3, 5)) for _ in range(n)) for _ in range(n)) + "\n" + rng.choice(["2", "5", "10"]) + "\n"


def table_pivot(rng, k):
    return "\n".join(f"{rng.choice(['north', 'south', 'east', 'west'])},{rng.choice(['q1', 'q2', 'q3', 'q4'])},{rng.randint(1, 1000)}" for _ in range(n_of(rng, k))) + "\n"


def cipher_in(rng, k):
    return str(rng.randint(1, 25)) + "\n" + text_lines(rng, k, rng.random() < 0.3)


def money_lines(rng, k):
    return "\n".join(f"{rng.choice(['item', 'tax', 'fee'])} {rng.randint(0, 99999) / 100:.2f}" for _ in range(n_of(rng, k))) + "\n"


def distinct_sorted(rng, k):
    n = n_of(rng, k)
    return " ".join(str(x) for x in sorted(rng.sample(range(1, 3 * n + 5), n))) + "\n"


def two_lists(rng, k):
    n = n_of(rng, k)
    return " ".join(str(rng.randint(1, 30)) for _ in range(n)) + "\n" + " ".join(str(rng.randint(1, 30)) for _ in range(n + rng.randint(-2, 2))) + "\n"


def pairs_str_int(rng, k):
    return "\n".join(f"{rng.choice(WORDS[:8])} {rng.randint(-5, 5)}" for _ in range(n_of(rng, k))) + "\n"


def seed_params(rng, k):
    return f"{rng.randint(1, 10 ** 6)} {[10, 50, 300][k]}\n"


def two_words_line(rng, k):
    return f"{rng.choice(WORDS)} {rng.choice(WORDS)}\n"


def temps(rng, k):
    return "\n".join(f"{rng.choice(['mon', 'tue', 'wed', 'thu', 'fri'])} {rng.randint(-10, 35)}" for _ in range(n_of(rng, k))) + "\n"


def opt_ints_lines(rng, k):
    return "\n".join(rng.choice(["5", "0", "-3", "7", "x", "", "2"]) for _ in range(n_of(rng, k))) + "\n"


def tuples_lines(rng, k):
    return "\n".join(f"{rng.randint(0, 9)},{rng.randint(0, 9)},{rng.choice(WORDS[:5])}" for _ in range(n_of(rng, k))) + "\n"


def cards(rng, k):
    return " ".join(rng.choice("23456789TJQKA") + rng.choice("SHDC") for _ in range(5)) + "\n"


def lines_of_cards(rng, k):
    return "\n".join(cards(rng, k).strip() for _ in range(n_of(rng, k) // 2 + 1)) + "\n"


def tokens_ops(rng, k):
    out = []
    for _ in range(n_of(rng, k)):
        out.append(" ".join(rng.choice([str(rng.randint(1, 9)), "+", "-", "*"]) for _ in range(rng.randint(1, 6))))
    return "\n".join(out) + "\n"
