import os

import alpha
import delta


def run():
    from pkg import leaf
    import pkg.leaf as dotted
    return leaf.value() + dotted.value() + len(os.sep)
