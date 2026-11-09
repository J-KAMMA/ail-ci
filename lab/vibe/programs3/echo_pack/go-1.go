package main

import (
	"encoding/binary"
	"io"
	"os"
)

func hashBytes(b []byte) uint32 {
	var h uint32
	for _, x := range b {
		h = h*257 + uint32(x) + 1
	}
	return h
}

func pack(input []byte) []byte {
	n := len(input)
	var out []byte
	out = append(out, 'E', 'P', '1')
	var tmp [4]byte
	binary.LittleEndian.PutUint32(tmp[:], uint32(n))
	out = append(out, tmp[:]...)

	positions := make(map[uint32][]int)
	inserted := 0
	insertUpTo := func(limit int) {
		for p := inserted; p < limit; p++ {
			if p+4 > n {
				break
			}
			k := uint32(input[p]) | uint32(input[p+1])<<8 | uint32(input[p+2])<<16 | uint32(input[p+3])<<24
			positions[k] = append(positions[k], p)
		}
		inserted = limit
	}

	lit := make([]byte, 0, 128)
	writeLit := func() {
		if len(lit) == 0 {
			return
		}
		out = append(out, byte(len(lit)-1))
		out = append(out, lit...)
		lit = lit[:0]
	}

	const maxCand = 8
	i := 0
	for i < n {
		insertUpTo(i)
		if i+4 <= n {
			k := uint32(input[i]) | uint32(input[i+1])<<8 | uint32(input[i+2])<<16 | uint32(input[i+3])<<24
			list := positions[k]
			maxLen := n - i
			if maxLen > 131 {
				maxLen = 131
			}
			bestM, bestP := 0, 0
			seen := 0
			for idx := len(list) - 1; idx >= 0 && seen < maxCand; idx-- {
				p := list[idx]
				if p >= i {
					continue
				}
				if i-p > 65535 {
					break
				}
				seen++
				m := 0
				for m < maxLen && input[p+m] == input[i+m] {
					m++
				}
				if m > bestM {
					bestM = m
					bestP = p
				}
			}
			if bestM >= 4 {
				writeLit()
				out = append(out, byte(0x80+bestM-4))
				dist := i - bestP
				out = append(out, byte(dist>>8), byte(dist))
				i += bestM
				continue
			}
		}
		lit = append(lit, input[i])
		if len(lit) == 128 {
			writeLit()
		}
		i++
	}
	writeLit()

	binary.LittleEndian.PutUint32(tmp[:], hashBytes(input))
	out = append(out, tmp[:]...)
	return out
}

func unpack(input []byte) ([]byte, bool) {
	if len(input) < 3 || input[0] != 'E' || input[1] != 'P' || input[2] != '1' {
		return nil, false
	}
	if len(input) < 7 {
		return nil, false
	}
	n := uint64(binary.LittleEndian.Uint32(input[3:7]))
	pos := 7
	var out []byte
	produced := uint64(0)
	for produced < n {
		if pos >= len(input) {
			return nil, false
		}
		c := input[pos]
		pos++
		if c < 0x80 {
			k := int(c) + 1
			if pos+k > len(input) {
				return nil, false
			}
			if produced+uint64(k) > n {
				return nil, false
			}
			out = append(out, input[pos:pos+k]...)
			pos += k
			produced += uint64(k)
		} else {
			length := int(c-0x80) + 4
			if pos+2 > len(input) {
				return nil, false
			}
			dist := int(input[pos])<<8 | int(input[pos+1])
			pos += 2
			if dist == 0 || uint64(dist) > produced {
				return nil, false
			}
			if produced+uint64(length) > n {
				return nil, false
			}
			for k := 0; k < length; k++ {
				out = append(out, out[len(out)-dist])
			}
			produced += uint64(length)
		}
	}
	if pos+4 > len(input) {
		return nil, false
	}
	stored := binary.LittleEndian.Uint32(input[pos : pos+4])
	pos += 4
	if pos != len(input) {
		return nil, false
	}
	if hashBytes(out) != stored {
		return nil, false
	}
	return out, true
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	switch os.Args[1] {
	case "pack":
		data, _ := io.ReadAll(os.Stdin)
		out := pack(data)
		os.Stdout.Write(out)
		os.Exit(0)
	case "unpack":
		data, _ := io.ReadAll(os.Stdin)
		out, ok := unpack(data)
		if !ok {
			os.Exit(2)
		}
		os.Stdout.Write(out)
		os.Exit(0)
	default:
		os.Exit(1)
	}
}
