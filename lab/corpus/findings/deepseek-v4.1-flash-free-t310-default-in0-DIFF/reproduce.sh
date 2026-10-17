#!/bin/sh
# from this directory; AIL=/path/to/ail_chatgpt.py
cp prog.py prog.ail
python3 "$AIL" compile prog.ail --syntax python -o prog_ail && ./prog_ail < input.txt
python3 prog.py < input.txt
