#!/bin/sh
# Reproduce the wedge3b venvs.  Two are incompatible, so they are separate.
set -e
ROOT=${1:-/tmp/w3b}
HERE=$(cd "$(dirname "$0")" && pwd)

mkdir -p "$ROOT"
cd "$ROOT"
python3 -m venv vpure
./vpure/bin/pip install -q --upgrade pip
./vpure/bin/pip install -q --no-binary pydantic -r "$HERE/requirements.txt"

# PyPy 3.10+ (the distro pypy3 on Ubuntu 24.04 is 3.9)
curl -sL -o pypy.tar.bz2 https://downloads.python.org/pypy/pypy3.10-v7.3.19-linux64.tar.bz2
tar xf pypy.tar.bz2
./pypy3.10-v7.3.19-linux64/bin/pypy3 -m venv vpypy
./vpypy/bin/pip install -q --upgrade pip
./vpypy/bin/pip install -q --no-binary pydantic pydantic==1.10.27 sqlparse==0.6.1

python3 -m venv vnative
./vnative/bin/pip install -q --upgrade pip
./vnative/bin/pip install -q 'pydantic==2.14.3' 'sqlglot[rs]==26.33.0'
