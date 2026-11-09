import jellyfish as j

pairs = [("", ""), ("a", ""), ("abc", "abc"), ("kitten", "sitting"),
         ("flux", "fluxx"), ("Smith", "Smyth"), ("1234", "1234"),
         ("O'Brien", "OBrien"), ("a" * 80, "a" * 79 + "b"), ("Robert", "Rupert")]
for a, b in pairs:
    print(repr(a), repr(b), j.levenshtein_distance(a, b),
          repr(j.jaro_winkler_similarity(a, b)), repr(j.soundex(a)))
d = {"a": "abc", "b": "abd"}
lst = [("x", "y"), ("abc", "abd")]
print("dict", j.levenshtein_distance(d["a"], d["b"]))
print("list", j.levenshtein_distance(*lst[1]))
