"""Compile AIL source to a standalone executable."""
import sys

from ail_chatgpt import main


if __name__ == '__main__':
    raise SystemExit(main(['compile', *sys.argv[1:]]))
