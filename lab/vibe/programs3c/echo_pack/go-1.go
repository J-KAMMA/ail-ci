package main

import (
	"encoding/binary"
	"io"
	"os"
)

func key(d []byte, i int) uint32 {
	return binary.LittleEndian.Uint32(d[i : i+4])
}

func hashOf(b []byte) uint32 {
	var h uint32
	for _, c := range b {
		h = h*257 + uint32(c) + 1
	}
	return h
}

func pack(d []byte) []byte {
	n := len(d)
	out := []byte{'E', 'P', '1', byte(n), byte(n >> 8), byte(n >> 16), byte(n >> 24)}
	var lit []byte
	flush := func() {
		if len(lit) > 0 {
			out = append(out, byte(len(lit)-1))
			out = append(out, lit...)
			lit = lit[:0]
		}
	}
	table := map[uint32][]int{}
	ins := 0
	i := 0
	for i < n {
		// insert all positions < i that have not been inserted yet
		for ins < i {
			if ins+4 <= n {
				k := key(d, ins)
				table[k] = append(table[k], ins)
			}
			ins++
		}
		bestLen, bestP := 0, -1
		if i+4 <= n {
			k := key(d, i)
			list := table[k]
			start := 0
			for start < len(list) && i-list[start] > 65535 {
				start++
			}
			list = list[start:]
			table[k] = list
			maxM := 131
			if n-i < maxM {
				maxM = n - i
			}
			cnt := 0
			for j := len(list) - 1; j >= 0 && cnt < 8; j-- {
				p := list[j]
				cnt++
				m := 0
				for m < maxM && d[p+m] == d[i+m] {
					m++
				}
				if m > bestLen {
					bestLen = m
					bestP = p
				}
			}
		}
		if bestP >= 0 {
			flush()
			dist := i - bestP
			out = append(out, byte(0x80+bestLen-4), byte(dist>>8), byte(dist))
			i += bestLen
		} else {
			lit = append(lit, d[i])
			if len(lit) == 128 {
				flush()
			}
			i++
		}
	}
	flush()
	h := hashOf(d)
	out = append(out, byte(h), byte(h>>8), byte(h>>16), byte(h>>24))
	return out
}

func unpack(in []byte) ([]byte, bool) {
	if len(in) < 3 || in[0] != 0x45 || in[1] != 0x50 || in[2] != 0x31 {
		return nil, false
	}
	if len(in) < 7 {
		return nil, false
	}
	n := int(binary.LittleEndian.Uint32(in[3:7]))
	pos := 7
	var out []byte
	for len(out) < n {
		if pos >= len(in) {
			return nil, false
		}
		c := in[pos]
		pos++
		if c < 0x80 {
			k := int(c) + 1
			if pos+k > len(in) {
				return nil, false
			}
			if len(out)+k > n {
				return nil, false
			}
			out = append(out, in[pos:pos+k]...)
			pos += k
		} else {
			if pos+2 > len(in) {
				return nil, false
			}
			dist := int(in[pos])<<8 | int(in[pos+1])
			pos += 2
			l := int(c-0x80) + 4
			if len(out)+l > n {
				return nil, false
			}
			if dist == 0 || dist > len(out) {
				return nil, false
			}
			for k := 0; k < l; k++ {
				out = append(out, out[len(out)-dist])
			}
		}
	}
	if len(in)-pos != 4 {
		return nil, false
	}
	want := binary.LittleEndian.Uint32(in[pos : pos+4])
	if hashOf(out) != want {
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
		data, err := io.ReadAll(os.Stdin)
		if err != nil {
			os.Exit(1)
		}
		res := pack(data)
		os.Stdout.Write(res)
		os.Exit(0)
	case "unpack":
		data, err := io.ReadAll(os.Stdin)
		if err != nil {
			os.Exit(2)
		}
		res, ok := unpack(data)
		if !ok {
			os.Exit(2)
		}
		os.Stdout.Write(res)
		os.Exit(0)
	default:
		os.Exit(1)
	}
}
