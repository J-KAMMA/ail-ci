# echo_pack

Write a command-line program:

    prog pack
    prog unpack

`pack` reads arbitrary bytes from standard input and writes their packed form (the "EP1" format
below) to standard output. `unpack` reads an EP1 stream from standard input, checks it, and writes
the original bytes to standard output. Both outputs are binary and must match byte for byte.

A wrong number of arguments (exactly one is required) or an argument other than `pack` / `unpack`:
write nothing to standard output and exit with status 1.

## EP1 format

1. Magic: the 3 bytes `45 50 31` (ASCII `EP1`).
2. Length: the number n of original bytes, as an unsigned 32-bit little-endian integer
   (4 bytes). Inputs to `pack` are shorter than 2^32 bytes.
3. Tokens, until exactly n bytes have been described:
   - *literal run*: a byte c in `00`..`7F`, followed by c + 1 bytes that are copied to the output
     as they are (1 to 128 bytes);
   - *copy*: a byte c in `80`..`FF`, followed by a 2-byte big-endian distance `dist`
     (1 .. 65535). It appends `len = (c - 0x80) + 4` bytes (4 .. 131): for k = 0 .. len-1, append
     the output byte at position (current output length - dist). Because this is done one byte at a
     time, the copy may overlap the bytes it is producing (dist 1 repeats the last byte).
4. Hash: an unsigned 32-bit little-endian integer h computed over the n original bytes b:
   start with h = 0 and for each byte do h = (h * 257 + b + 1) mod 2^32.

## pack: choosing the tokens (must be followed exactly)

Let D[0..n-1] be the input. Positions are processed from i = 0; a pending literal buffer L starts
empty.

At position i:

- If i + 4 <= n, the *candidates* are the positions p with p < i, i - p <= 65535 and
  D[p..p+3] = D[i..i+3] (the 4 bytes starting at p equal the 4 bytes starting at i). Only the
  **8 largest** such p are considered (all of them if there are fewer than 8).
- For each considered candidate p, its *match length* is the largest m <= min(131, n - i) with
  D[p+k] = D[i+k] for all k < m. (p + k may reach i or beyond; the comparison is made on the
  input D, so overlapping matches are found too.) Every considered candidate has m >= 4.
- If there is at least one considered candidate, take the largest match length; among candidates
  with that length, take the largest p. Then: if L is not empty, emit L as a literal run
  (see below) and empty it; emit a copy token with length m and dist = i - p; continue at i + m.
- Otherwise (i + 4 > n, or no candidate) append D[i] to L; if L now holds 128 bytes, emit it as a
  literal run and empty it; continue at i + 1.

When i reaches n, emit L if it is not empty. A literal run of k bytes (1 <= k <= 128) is the byte
k - 1 followed by the k bytes. Then write the hash. So the empty input packs to the 11 bytes
`45 50 31 00 00 00 00 00 00 00 00`.

Note that positions inside a copy are skipped as starting points but are still candidates for
later positions: the candidate rule above refers only to the input bytes.

## unpack: checking

`unpack` must reject, by writing nothing at all to standard output and exiting with status 2,
any input that is not exactly one valid EP1 stream:

- shorter than 3 bytes or wrong magic; fewer than 4 length bytes;
- a token or its operand bytes (literal bytes, distance bytes) cut off by the end of the input;
- a literal run or a copy that would make the output longer than n;
- a copy with dist = 0 or dist greater than the number of bytes produced so far;
- fewer than 4 hash bytes after the tokens, or the hash does not match the produced bytes;
- any bytes after the hash.

Valid streams need not come from `pack` (for example a literal run may be shorter than possible,
or a copy may be used where `pack` would not use one); `unpack` accepts every stream that follows
the format. On success write the n bytes and exit with status 0; `pack` always exits with
status 0.
