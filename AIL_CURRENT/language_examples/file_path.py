"""The path a Python-syntax program was built from, as CPython reports it."""
from pathlib import Path

SOURCE = Path(__file__)
print(SOURCE.name)
print(SOURCE.suffix)
print(SOURCE.resolve().name)
print(__file__ == str(SOURCE))
print(SOURCE.parent.name)
