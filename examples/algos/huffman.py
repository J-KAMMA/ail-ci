"""Huffman coding: code lengths and total encoded bits for generated text."""
import heapq
import sys

SMALL = "--small" in sys.argv
TEXT_LEN = 20_000 if SMALL else 4_000_000
ALPHABET = "abcdefghijklmnopqrstuvwxyz .,!?"

seed = 314159


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def generate(length):
    chars = []
    for _ in range(length):
        chars.append(ALPHABET[rnd() % len(ALPHABET)])
    return "".join(chars)


def code_lengths(text):
    frequencies = {}
    for ch in text:
        frequencies[ch] = frequencies.get(ch, 0) + 1
    order = 0
    heap = []
    for ch, count in frequencies.items():
        heap.append((count, order, ch))
        order += 1
    heapq.heapify(heap)
    while len(heap) > 1:
        left_count, _, left = heapq.heappop(heap)
        right_count, _, right = heapq.heappop(heap)
        merged = (left, right)
        heapq.heappush(heap, (left_count + right_count, order, merged))
        order += 1
    lengths = {}
    stack = [(heap[0][2], 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, str):
            lengths[node] = depth
        else:
            stack.append((node[0], depth + 1))
            stack.append((node[1], depth + 1))
    return frequencies, lengths


text = generate(TEXT_LEN)
frequencies, lengths = code_lengths(text)
total_bits = 0
longest = 0
shortest = None
for ch, count in frequencies.items():
    total_bits += count * lengths[ch]
    if lengths[ch] > longest:
        longest = lengths[ch]
    if shortest is None or lengths[ch] < shortest:
        shortest = lengths[ch]

print("chars", TEXT_LEN)
print("symbols", len(frequencies))
print("bits", total_bits)
print("bytes", (total_bits + 7) // 8)
print("shortest", shortest)
print("longest", longest)
