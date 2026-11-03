#!/usr/bin/env python3
"""Compatibility wrapper for the `ail convert` converter core (AIL_CURRENT/ail2py.py)."""
import importlib.util
from pathlib import Path

_core_path = Path(__file__).resolve().parent.parent / 'AIL_CURRENT' / 'ail2py.py'
_spec = importlib.util.spec_from_file_location('_ail2py_core', _core_path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

for _name, _value in list(vars(_core).items()):
    if not _name.startswith('__'):
        globals()[_name] = _value
main = _core.main

if __name__ == '__main__':
    raise SystemExit(main())
