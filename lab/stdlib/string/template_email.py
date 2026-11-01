import string

EMAIL = string.Template(
    "Dear $name,\n"
    "Your order ${order} totals $$${amount}.\n"
    "Thanks, $team\n"
)


def render(template, **values):
    return template.substitute(values)


def main():
    print(render(EMAIL, name="Ada", order="A-17", amount="12.50", team="Example Store"))
    print(EMAIL.safe_substitute(name="Grace"))
    print(EMAIL.template)
    print(sorted(EMAIL.get_identifiers()))
    try:
        EMAIL.substitute(name="Ada")
    except KeyError as exc:
        print("KeyError", exc)
    try:
        string.Template("$").substitute()
    except ValueError as exc:
        print("ValueError", exc)


main()
