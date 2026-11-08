"""Driver for field_valid: validate a generated batch of records."""
import field_valid as m

NAMES = ["  Ada   Lovelace ", "Grace  Hopper", "Alan  Turing", "edsger  dijkstra"]
EMAILS = ["ada@example.com", "grace@example.org", "alan@example.com", "edsger@example.org"]
TAGS = ["1.2.3", "0.9", "3.4.5"]
BATCH = 700000


def main() -> None:
    good = 0
    weight = 0
    upper = 0
    email_ok = 0
    version_ok = 0
    for i in range(BATCH):
        raw = NAMES[i % 4]
        name = m.normalise_name(raw)
        score = i % 101
        email = EMAILS[i % 4]
        tag = TAGS[i % 3]
        if m.valid_len(name) and m.score_ok(score) and m.is_simple_email(email):
            good += 1
        if m.is_upper_name(name):
            upper += 1
        if m.looks_like_version(tag):
            version_ok += 1
        if m.is_simple_email(email):
            email_ok += 1
        weight += m.field_weight(name, score, email)
    print("good", good)
    print("upper", upper)
    print("email_ok", email_ok)
    print("version_ok", version_ok)
    print("weight", weight)


main()
