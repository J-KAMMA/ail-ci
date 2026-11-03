"""The subset of AIL_CURRENT/ail.py that the compare-lab tasks import, for Codon.

Codon cannot import the CPython-only helpers (select, socket, struct, heapq), so this file supplies
the same behaviour for wrapping arithmetic, the keyed heap and stdin/stdout/file bytes.  The task
sources are unchanged: Codon compiles the same typed.py that AIL compiles, with this module on
PYTHONPATH in place of AIL_CURRENT/ail.py.
"""
import os

# Codon's int is a signed 64-bit integer and wraps on overflow, like AIL's default int; the
# explicit modulo in AIL_CURRENT/ail.py would need a 65-bit temporary and cannot be used here.

def wrapping_add(a: int, b: int) -> int:
    return a + b

def wrapping_sub(a: int, b: int) -> int:
    return a - b

def wrapping_mul(a: int, b: int) -> int:
    return a * b

def _key_lt(a, b, key):
    return key(a) < key(b) if key is not None else a < b

def _siftdown(heap, startpos, pos, key):
    newitem = heap[pos]
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if _key_lt(newitem, parent, key):
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem

def _siftup(heap, pos, key):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos and not _key_lt(heap[childpos], heap[rightpos], key):
            childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown(heap, startpos, pos, key)

def heappush(heap, item, key=None):
    if key is None:
        heap.append(item)
        _siftdown(heap, 0, len(heap) - 1, key)
        return
    heap.append(item)
    _siftdown(heap, 0, len(heap) - 1, key)

def heappop(heap, key=None):
    if not heap:
        raise IndexError('pop from an empty heap')
    last = heap.pop()
    if not heap:
        return last
    root = heap[0]
    heap[0] = last
    _siftup(heap, 0, key)
    return root

def read_stdin_bytes(size):
    out = bytearray()
    remaining = size
    while remaining > 0:
        data = os.read(0, min(remaining, 1 << 20))
        if not data:
            break
        out.extend(data)
        remaining -= len(data)
    return bytes(out)

def write_stdout_bytes(data):
    done = 0
    while done < len(data):
        done += os.write(1, bytes(data[done:]))

def read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()
