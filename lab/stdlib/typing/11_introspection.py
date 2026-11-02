from typing import Dict, List, Optional, Tuple, Union, get_args, get_origin


def main() -> None:
    print(get_origin(List[int]))
    print(get_args(List[int]))
    print(get_origin(Dict[str, int]))
    print(get_args(Dict[str, int]))
    print(get_origin(Optional[int]))
    print(get_args(Optional[int]))
    print(get_origin(Union[int, str]))
    print(get_args(Union[int, str]))
    print(get_origin(Tuple[int, str]))
    print(get_args(Tuple[int, str]))
    print(get_origin(int))
    print(get_args(int))


main()
