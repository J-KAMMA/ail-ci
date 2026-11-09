package main

import (
	"encoding/binary"
	"io"
	"os"
)

func key4(d []byte, i int) uint32 {
	return uint32(d[i]) | uint32(d[i+1])<<8 | uint32(d[i+2])<<16 | uint32(d[i+3])<<24
}

func hashOf(d []byte) uint32 {
	var h uint32
	for _, b := range d {
		h = h*257 + uint32(b) + 1
	}
	return h
}

func pack(d []byte) []byte {
	n := len(d)
	out := make([]byte, 0, n+n/128+64)
	out = append(out, 'E', 'P', '1')
	var nb [4]byte
	binary.LittleEndian.PutUint32(nb[:], uint32(n))
	out = append(out, nb[:]...)

	var lit []byte
	flush := func() {
		if len(lit) > 0 {
			out = append(out, byte(len(lit)-1))
			out = append(out, lit...)
			lit = lit[:0]
		}
	}

	pos := make(map[uint32][]int)
	inserted := 0
	insertUpTo := func(i int) {
		for ; inserted < i; inserted++ {
			if inserted+4 <= n {
				k := key4(d, inserted)
				pos[k] = append(pos[k], inserted)
			}
		}
	}

	i := 0
	for i < n {
		bestM, bestP := 0, -1
		if i+4 <= n {
			insertUpTo(i)
			list := pos[key4(d, i)]
			maxm := 131
			if n-i < maxm {
				maxm = n - i
			}
			cnt := 0
			for j := len(list) - 1; j >= 0 && cnt < 8; j-- {
				p := list[j]
				if i-p > 65535 {
					break
				}
				cnt++
				m := 0
				for m < maxm && d[p+m] == d[i+m] {
					m++
				}
				if m > bestM {
					bestM, bestP = m, p
				}
			}
		}
		if bestP >= 0 {
			flush()
			dist := i - bestP
			out = append(out, byte(0x80+bestM-4), byte(dist>>8), byte(dist))
			i += bestM
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
	var hb [4]byte
	binary.LittleEndian.PutUint32(hb[:], h)
	out = append(out, hb[:]...)
	return out
}

func unpack(b []byte) ([]byte, bool) {
	if len(b) < 7 || b[0] != 0x45 || b[1] != 0x50 || b[2] != 0x31 {
		return nil, false
	}
	n := int(binary.LittleEndian.Uint32(b[3:7]))
	pos := 7
	out := make([]byte, 0, 1024)
	for len(out) < n {
		if pos >= len(b) {
			return nil, false
		}
		c := b[pos]
		pos++
		if c < 0x80 {
			k := int(c) + 1
			if pos+k > len(b) {
				return nil, false
			}
			if len(out)+k > n {
				return nil, false
			}
			out = append(out, b[pos:pos+k]...)
			pos += k
		} else {
			if pos+2 > len(b) {
				return nil, false
			}
			dist := int(b[pos])<<8 | int(b[pos+1])
			pos += 2
			ln := int(c-0x80) + 4
			if len(out)+ln > n {
				return nil, false
			}
			if dist == 0 || dist > len(out) {
				return nil, false
			}
			for k := 0; k < ln; k++ {
				out = append(out, out[len(out)-dist])
			}
		}
	}
	if len(b)-pos != 4 {
		return nil, false
	}
	want := binary.LittleEndian.Uint32(b[pos : pos+4])
	if hashOf(out) != want {
		return nil, false
	}
	return out, true
}

func main() {
	args := os.Args
	if len(args) != 2 {
		os.Exit(1)
	}
	switch args[1] {
	case "pack":
		data, _ := io.ReadAll(os.Stdin)
		os.Stdout.Write(pack(data))
		os.Exit(0)
	case "unpack":
		data, _ := io.ReadAll(os.Stdin)
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
