"""The `_heapq` accelerator, written in the Python subset: what CPython's C module does, error texts included.

CPython's heapq.py runs `from _heapq import *` and so replaces its pure-Python heappush/heappop/... by the C
ones, which differ from the pure-Python ones in what they raise (`IndexError: index out of range`, `TypeError:
heappop() argument must be list, not tuple`). This file has the C module's behaviour, so the import in heapq.py
succeeds as in CPython and the program prints what CPython prints. Not matched: the text of a call with the wrong
number of arguments (the compiler refuses such a call), keyword arguments.
"""
__all__ = ['heappush', 'heappop', 'heapify', 'heapreplace', 'heappushpop']


def _tn(x):
    if x is None:
        return 'None'
    name = type(x).__name__
    if name == '_ail_object':
        return 'object'          # the compiler's object() sentinel
    return name


def _siftdown(heap, startpos, pos):
    newitem = heap[pos]
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if newitem < parent:
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem


def _siftup(heap, pos):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos and not heap[childpos] < heap[rightpos]:
            childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown(heap, startpos, pos)


def _siftdown_max(heap, startpos, pos):
    newitem = heap[pos]
    while pos > startpos:
        parentpos = (pos - 1) >> 1
        parent = heap[parentpos]
        if parent < newitem:
            heap[pos] = parent
            pos = parentpos
            continue
        break
    heap[pos] = newitem


def _siftup_max(heap, pos):
    endpos = len(heap)
    startpos = pos
    newitem = heap[pos]
    childpos = 2 * pos + 1
    while childpos < endpos:
        rightpos = childpos + 1
        if rightpos < endpos and not heap[rightpos] < heap[childpos]:
            childpos = rightpos
        heap[pos] = heap[childpos]
        pos = childpos
        childpos = 2 * pos + 1
    heap[pos] = newitem
    _siftdown_max(heap, startpos, pos)


def heappush(heap, item, /):
    if not isinstance(heap, list):
        raise TypeError('heappush() argument 1 must be list, not ' + _tn(heap))
    heap.append(item)
    _siftdown(heap, 0, len(heap) - 1)


def heappop(heap, /):
    if not isinstance(heap, list):
        raise TypeError('heappop() argument must be list, not ' + _tn(heap))
    if len(heap) == 0:
        raise IndexError('index out of range')
    lastelt = heap.pop()
    if heap:
        returnitem = heap[0]
        heap[0] = lastelt
        _siftup(heap, 0)
        return returnitem
    return lastelt


def heapreplace(heap, item, /):
    if not isinstance(heap, list):
        raise TypeError('heapreplace() argument 1 must be list, not ' + _tn(heap))
    if len(heap) == 0:
        raise IndexError('index out of range')
    returnitem = heap[0]
    heap[0] = item
    _siftup(heap, 0)
    return returnitem


def heappushpop(heap, item, /):
    if not isinstance(heap, list):
        raise TypeError('heappushpop() argument 1 must be list, not ' + _tn(heap))
    if len(heap) == 0 or not heap[0] < item:
        return item
    returnitem = heap[0]
    heap[0] = item
    _siftup(heap, 0)
    return returnitem


def heapify(heap, /):
    if not isinstance(heap, list):
        raise TypeError('heapify() argument must be list, not ' + _tn(heap))
    n = len(heap)
    i = n // 2 - 1
    while i >= 0:
        _siftup(heap, i)
        i -= 1


def _heappop_max(heap, /):
    if not isinstance(heap, list):
        raise TypeError('_heappop_max() argument must be list, not ' + _tn(heap))
    if len(heap) == 0:
        raise IndexError('index out of range')
    lastelt = heap.pop()
    if heap:
        returnitem = heap[0]
        heap[0] = lastelt
        _siftup_max(heap, 0)
        return returnitem
    return lastelt


def _heapreplace_max(heap, item, /):
    if not isinstance(heap, list):
        raise TypeError('_heapreplace_max() argument 1 must be list, not ' + _tn(heap))
    if len(heap) == 0:
        raise IndexError('index out of range')
    returnitem = heap[0]
    heap[0] = item
    _siftup_max(heap, 0)
    return returnitem


def _heapify_max(heap, /):
    if not isinstance(heap, list):
        raise TypeError('_heapify_max() argument must be list, not ' + _tn(heap))
    n = len(heap)
    i = n // 2 - 1
    while i >= 0:
        _siftup_max(heap, i)
        i -= 1
