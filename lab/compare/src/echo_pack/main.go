package main

import (
	"bufio"
	"encoding/binary"
	"io"
	"os"
)

func hashOf(b []byte) uint32 {
	var h uint32
	for _, c := range b {
		h = h*257 + uint32(c) + 1
	}
	return h
}

func pack(d []byte) []byte {
	n := len(d)
	out := make([]byte, 0, n/2+16)
	out = append(out, 'E', 'P', '1', 0, 0, 0, 0)
	binary.LittleEndian.PutUint32(out[3:], uint32(n))
	head := make(map[uint32]int32)
	prev := make([]int32, n)
	inserted := 0
	insertUpTo := func(lim int) { // insert positions < lim
		for inserted < lim {
			p := inserted
			inserted++
			if p+4 > n {
				continue
			}
			k := binary.LittleEndian.Uint32(d[p:])
			if h, ok := head[k]; ok {
				prev[p] = h
			} else {
				prev[p] = -1
			}
			head[k] = int32(p)
		}
	}
	var lit []byte
	flush := func() {
		if len(lit) > 0 {
			out = append(out, byte(len(lit)-1))
			out = append(out, lit...)
			lit = lit[:0]
		}
	}
	i := 0
	for i < n {
		bestM, bestP := 0, -1
		if i+4 <= n {
			insertUpTo(i)
			k := binary.LittleEndian.Uint32(d[i:])
			p := -1
			if h, ok := head[k]; ok {
				p = int(h)
			}
			maxm := n - i
			if maxm > 131 {
				maxm = 131
			}
			for cnt := 0; cnt < 8 && p >= 0 && i-p <= 65535; cnt++ {
				m := 4
				for m < maxm && d[p+m] == d[i+m] {
					m++
				}
				if m > bestM {
					bestM, bestP = m, p
				}
				p = int(prev[p])
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
	var hb [4]byte
	binary.LittleEndian.PutUint32(hb[:], hashOf(d))
	return append(out, hb[:]...)
}

func unpack(s []byte) ([]byte, bool) {
	if len(s) < 7 || s[0] != 'E' || s[1] != 'P' || s[2] != '1' {
		return nil, false
	}
	n := uint64(binary.LittleEndian.Uint32(s[3:]))
	pos := 7
	out := make([]byte, 0)
	for uint64(len(out)) < n {
		if pos >= len(s) {
			return nil, false
		}
		c := int(s[pos])
		pos++
		if c < 0x80 {
			l := c + 1
			if pos+l > len(s) || uint64(len(out)+l) > n {
				return nil, false
			}
			out = append(out, s[pos:pos+l]...)
			pos += l
		} else {
			l := c - 0x80 + 4
			if pos+2 > len(s) {
				return nil, false
			}
			dist := int(s[pos])<<8 | int(s[pos+1])
			pos += 2
			if dist == 0 || dist > len(out) || uint64(len(out)+l) > n {
				return nil, false
			}
			for k := 0; k < l; k++ {
				out = append(out, out[len(out)-dist])
			}
		}
	}
	if len(s)-pos != 4 {
		return nil, false
	}
	if binary.LittleEndian.Uint32(s[pos:]) != hashOf(out) {
		return nil, false
	}
	return out, true
}

func main() {
	if len(os.Args) != 2 || (os.Args[1] != "pack" && os.Args[1] != "unpack") {
		os.Exit(1)
	}
	in, _ := io.ReadAll(bufio.NewReaderSize(os.Stdin, 1<<20))
	w := bufio.NewWriterSize(os.Stdout, 1<<20)
	if os.Args[1] == "pack" {
		w.Write(pack(in))
		w.Flush()
		return
	}
	res, ok := unpack(in)
	if !ok {
		os.Exit(2)
	}
	w.Write(res)
	w.Flush()
}
