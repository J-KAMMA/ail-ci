import os

import alpha
import delta


def run():
    from pkg import leaf
    return leaf.value() + len(os.sep)
