class C:
    def lower(self):
        return list(dict(enumerate("xxxxxxxxxxxxxxxxxxxxx")))


def through_dict_value():
    d = {"a": C().lower()}
    for k in d["a"]:
        print(k ** k)


def directly():
    for k in C().lower():
        print(k ** k)


through_dict_value()
directly()
