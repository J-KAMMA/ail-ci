"""Byte-level BPE tokenizer in AIL: GPT-2 (and the zenz GPT-2 variant), id-exact.

The program and its module share one implementation.  A vocabulary directory
holds `vocab.json` (token -> id) and `merges.txt` (ranked merges, with an
optional `#version:` header), the same two files Hugging Face `tokenizers` and
llama.cpp read.

Usage:
    bpe.py encode VOCAB_DIR TEXT_FILE
    bpe.py decode VOCAB_DIR IDS_FILE
    bpe.py roundtrip VOCAB_DIR TEXT_FILE

`encode` prints one line per input line: the token ids separated by spaces.
`decode` prints the bytes those ids make.  `roundtrip` encodes and decodes and
prints the recovered bytes, so callers can compare it with the input.

The pre-tokenizer is the GPT-2 pattern written as plain code:

    's|'t|'re|'ve|'m|'ll|'d| ?\\p{L}+| ?\\p{N}+| ?[^\\s\\p{L}\\p{N}]+|\\s+(?!\\S)|\\s+

A literal ASCII space before a letter, number or punctuation run is part of
that run (rules 2-4).  A whitespace run before a non-space is split as
`k - 1` whitespace (rule 5) and its last character, which then either starts
the next run (when it is a space) or is a one-character whitespace token
(rule 6).  A whitespace run at the end of the text is one token.  The
classifiers are Python's Unicode definitions: `isalpha` is general category
L, `isnumeric` is N, and `isspace` is `\\s`.  llama.cpp's
`gpt2-small-japanese-char` pre-tokenizer is this same expression in the pinned
azooKey fork, so zenz uses the same splitter.

Input is walked as UTF-8 bytes so that the 16-bit general build and the typed
build both handle astral text (emoji in the corpus).  A code point above
U+FFFF is classified as punctuation/symbol, which is exact for the corpus
(pictographs) and is the only classification the 16-bit runtime can make;
non-BMP letters would not be grouped as letters.  Decode writes raw bytes for
the same reason.
"""
import json
import sys

from ail import read_bytes, write_stdout_bytes

BYTE_CHARS = '\u0100\u0101\u0102\u0103\u0104\u0105\u0106\u0107\u0108\u0109\u010a\u010b\u010c\u010d\u010e\u010f\u0110\u0111\u0112\u0113\u0114\u0115\u0116\u0117\u0118\u0119\u011a\u011b\u011c\u011d\u011e\u011f\u0120!"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~\u0121\u0122\u0123\u0124\u0125\u0126\u0127\u0128\u0129\u012a\u012b\u012c\u012d\u012e\u012f\u0130\u0131\u0132\u0133\u0134\u0135\u0136\u0137\u0138\u0139\u013a\u013b\u013c\u013d\u013e\u013f\u0140\u0141\u0142\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\u0143\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'


def byte_char(value: int) -> str:
    """GPT-2's byte-to-unicode character for one byte (the 256-character table)."""
    return BYTE_CHARS[value]


def build_byte_index() -> dict[str, int]:
    """The inverse of BYTE_CHARS, built once from the table."""
    index: dict[str, int] = {}
    value = 0
    while value < 256:
        index[BYTE_CHARS[value]] = value
        value += 1
    return index


def load_vocab(path: str) -> dict[str, int]:
    data: dict[str, int] = json.loads(read_bytes(path).decode())
    return data


def load_ranks(path: str) -> dict[str, int]:
    text = read_bytes(path).decode()
    lines = text.split("\n")
    ranks: dict[str, int] = {}
    rank = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if len(line) > 0 and line[0] != "#":
            parts = line.split(" ")
            if len(parts) == 2:
                ranks[parts[0] + "\x00" + parts[1]] = rank
                rank += 1
        index += 1
    return ranks


def split_lines(data: bytes) -> list[bytes]:
    """Split on LF, dropping one CR before it; a final LF makes no empty line."""
    lines: list[bytes] = []
    start = 0
    index = 0
    while index < len(data):
        if data[index] == 10:
            end = index
            if end > start and data[end - 1] == 13:
                end -= 1
            lines.append(data[start:end])
            start = index + 1
        index += 1
    if start < len(data):
        end = len(data)
        if end > start and data[end - 1] == 13:
            end -= 1
        lines.append(data[start:end])
    return lines


def utf8_at(data: bytes, start: int, size: int) -> int:
    """The code point at `start`; a truncated or invalid sequence becomes its first byte."""
    lead = data[start]
    if lead < 128:
        return lead
    if lead >= 194 and lead <= 223 and start + 1 < size:
        return ((lead & 31) << 6) | (data[start + 1] & 63)
    if lead >= 224 and lead <= 239 and start + 2 < size:
        return ((lead & 15) << 12) | ((data[start + 1] & 63) << 6) | (data[start + 2] & 63)
    if lead >= 240 and lead <= 244 and start + 3 < size:
        return ((lead & 7) << 18) | ((data[start + 1] & 63) << 12) | ((data[start + 2] & 63) << 6) | (data[start + 3] & 63)
    return lead


def utf8_width(code: int) -> int:
    if code < 128:
        return 1
    if code < 2048:
        return 2
    if code < 65536:
        return 3
    return 4


def is_space_code(code: int) -> bool:
    if code > 65535:
        return False
    character = chr(code)
    return character.isspace()


def is_alpha_code(code: int) -> bool:
    if code > 65535:
        return False
    character = chr(code)
    return character.isalpha()


def is_numeric_code(code: int) -> bool:
    if code > 65535:
        return False
    character = chr(code)
    return character.isnumeric()


def is_plain_code(code: int) -> bool:
    return (not is_space_code(code)) and (not is_alpha_code(code)) and (not is_numeric_code(code))


def pre_tokenize(data: bytes) -> list[bytes]:
    pieces: list[bytes] = []
    size = len(data)
    index = 0
    while index < size:
        code = utf8_at(data, index, size)
        width = utf8_width(code)
        if code == 39 and index + width < size:
            following = utf8_at(data, index + width, size)
            matched = 0
            if following == 115 or following == 116 or following == 109 or following == 100:
                matched = 2
            elif (following == 114 or following == 118) and index + width + 1 < size and data[index + width + 1] == 101:
                matched = 3
            elif following == 108 and index + width + 1 < size and data[index + width + 1] == 108:
                matched = 3
            if matched != 0:
                pieces.append(data[index:index + matched])
                index += matched
                continue
        if code == 32 and index + 1 < size:
            following = utf8_at(data, index + 1, size)
            following_width = utf8_width(following)
            if is_alpha_code(following):
                end = index + 1 + following_width
                while end < size:
                    other = utf8_at(data, end, size)
                    if not is_alpha_code(other):
                        break
                    end += utf8_width(other)
                pieces.append(data[index:end])
                index = end
                continue
            if is_numeric_code(following):
                end = index + 1 + following_width
                while end < size:
                    other = utf8_at(data, end, size)
                    if not is_numeric_code(other):
                        break
                    end += utf8_width(other)
                pieces.append(data[index:end])
                index = end
                continue
            if is_plain_code(following):
                end = index + 1 + following_width
                while end < size:
                    other = utf8_at(data, end, size)
                    if not is_plain_code(other):
                        break
                    end += utf8_width(other)
                pieces.append(data[index:end])
                index = end
                continue
        if is_alpha_code(code):
            end = index + width
            while end < size:
                other = utf8_at(data, end, size)
                if not is_alpha_code(other):
                    break
                end += utf8_width(other)
            pieces.append(data[index:end])
            index = end
            continue
        if is_numeric_code(code):
            end = index + width
            while end < size:
                other = utf8_at(data, end, size)
                if not is_numeric_code(other):
                    break
                end += utf8_width(other)
            pieces.append(data[index:end])
            index = end
            continue
        if is_plain_code(code):
            end = index + width
            while end < size:
                other = utf8_at(data, end, size)
                if not is_plain_code(other):
                    break
                end += utf8_width(other)
            pieces.append(data[index:end])
            index = end
            continue
        if is_space_code(code):
            end = index
            last_start = index
            count = 0
            while end < size:
                other = utf8_at(data, end, size)
                if not is_space_code(other):
                    break
                last_start = end
                count += 1
                end += utf8_width(other)
            if end >= size:
                pieces.append(data[index:end])
                index = end
                continue
            if count >= 2:
                pieces.append(data[index:last_start])
                index = last_start
                continue
            pieces.append(data[index:end])
            index = end
            continue
        pieces.append(data[index:index + width])
        index += width
    return pieces


def merge_word(word: bytes, ranks: dict[str, int]) -> str:
    """BPE merges by lowest-rank pair, merging every occurrence; tokens joined by NUL."""
    characters: list[str] = []
    for value in word:
        characters.append(byte_char(value))
    while len(characters) > 1:
        best_rank = -1
        best_at = -1
        position = 0
        while position < len(characters) - 1:
            key = characters[position] + "\x00" + characters[position + 1]
            if key in ranks:
                rank = ranks[key]
                if best_rank < 0 or rank < best_rank:
                    best_rank = rank
                    best_at = position
            position += 1
        if best_at < 0:
            break
        first = characters[best_at]
        second = characters[best_at + 1]
        merged = first + second
        next_characters: list[str] = []
        position = 0
        while position < len(characters):
            if position + 1 < len(characters) and characters[position] == first and characters[position + 1] == second:
                next_characters.append(merged)
                position += 2
            else:
                next_characters.append(characters[position])
                position += 1
        characters = next_characters
    return "\x00".join(characters)


def encode_line(data: bytes, vocab: dict[str, int], ranks: dict[str, int]) -> list[int]:
    ids: list[int] = []
    pieces = pre_tokenize(data)
    index = 0
    while index < len(pieces):
        joined = merge_word(pieces[index], ranks)
        for token in joined.split("\x00"):
            if token in vocab:
                ids.append(vocab[token])
        index += 1
    return ids


def decode_ids(ids: list[int], inverse: dict[int, str], byte_index: dict[str, int]) -> bytes:
    raw = bytearray()
    index = 0
    while index < len(ids):
        token = inverse[ids[index]]
        for character in token:
            raw.append(byte_index[character])
        index += 1
    return bytes(raw)


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: bpe.py encode|decode|roundtrip VOCAB_DIR FILE", file=sys.stderr)
        return 2
    command = sys.argv[1]
    directory = sys.argv[2]
    path = sys.argv[3]
    vocab = load_vocab(directory + "/vocab.json")
    ranks = load_ranks(directory + "/merges.txt")
    inverse: dict[int, str] = {}
    for token in vocab:
        inverse[vocab[token]] = token
    byte_index = build_byte_index()
    lines = split_lines(read_bytes(path))
    if command == "encode":
        index = 0
        while index < len(lines):
            ids = encode_line(lines[index], vocab, ranks)
            parts: list[str] = []
            position = 0
            while position < len(ids):
                parts.append(str(ids[position]))
                position += 1
            print(" ".join(parts))
            index += 1
        return 0
    if command == "decode":
        index = 0
        while index < len(lines):
            words = lines[index].split()
            ids: list[int] = []
            position = 0
            while position < len(words):
                ids.append(int(words[position]))
                position += 1
            write_stdout_bytes(decode_ids(ids, inverse, byte_index) + b"\n")
            index += 1
        return 0
    if command == "roundtrip":
        index = 0
        while index < len(lines):
            ids = encode_line(lines[index], vocab, ranks)
            write_stdout_bytes(decode_ids(ids, inverse, byte_index) + b"\n")
            index += 1
        return 0
    print("refused: unknown command " + command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
