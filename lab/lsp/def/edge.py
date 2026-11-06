vals = [1, 2]
same = [vals for vals in vals]
emoji = "😀"; target = 1


def g():
    return target


def handler():
    try:
        return 1
    except ValueError as err:
        return err


def matcher(value):
    match value:
        case {"key": val}:
            return val
