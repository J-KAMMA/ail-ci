package main

import (
	"fmt"
	"os"
	"sort"
)

type rec struct {
	off    int
	op     byte
	a, b, c uint64
	name   string
}

type acct struct {
	id   uint32
	name string
	bal  int64
	shut bool
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	fail := func(off int, kind string) {
		fmt.Printf("error at offset %d: %s\n", off, kind)
		os.Exit(2)
	}
	if len(data) < 6 || data[0] != 0xC7 || data[1] != 'L' || data[2] != 'X' || data[3] != 'F' || data[4] != 2 || data[5] > 1 {
		fail(0, "header")
	}
	strict := data[5] == 1
	n := len(data)
	pos := 6
	var recs []rec
	for pos < n {
		x := pos
		p := pos
		kind := ""
		readVar := func() uint64 {
			var v uint64
			for i := 0; i < 5; i++ {
				if p >= n {
					fail(x, "truncated")
				}
				b := data[p]
				p++
				if i == 4 && b&0x80 != 0 {
					fail(x, "varint")
				}
				v |= uint64(b&0x7F) << (7 * uint(i))
				if b&0x80 == 0 {
					if i >= 1 && b == 0 {
						fail(x, "varint")
					}
					if v > 4294967295 {
						fail(x, "varint")
					}
					return v
				}
			}
			return 0
		}
		_ = kind
		r := rec{off: x, op: data[p]}
		p++
		switch r.op {
		case 1:
			r.a = readVar()
			if p >= n {
				fail(x, "truncated")
			}
			nl := int(data[p])
			p++
			if nl < 1 || nl > 32 {
				fail(x, "name")
			}
			bs := make([]byte, 0, nl)
			for i := 0; i < nl; i++ {
				if p >= n {
					fail(x, "truncated")
				}
				c := data[p]
				p++
				if c < 0x21 || c > 0x7E {
					fail(x, "name")
				}
				bs = append(bs, c)
			}
			r.name = string(bs)
			r.b = readVar()
		case 2:
			r.a = readVar()
			r.b = readVar()
			r.c = readVar()
		case 3:
			r.a = readVar()
		case 4:
			r.a = readVar()
			r.b = readVar()
		case 5:
			l := readVar()
			if uint64(n-p) < l {
				fail(x, "truncated")
			}
			p += int(l)
		default:
			fail(x, "opcode")
		}
		if p >= n {
			fail(x, "truncated")
		}
		c := 0
		for i := x; i < p; i++ {
			c = (c*31 + int(data[i])) % 251
		}
		if int(data[p]) != c {
			fail(x, "check")
		}
		p++
		pos = p
		recs = append(recs, r)
	}

	accts := map[uint32]*acct{}
	rej := map[string]int{}
	reject := func(off int, reason string) {
		if strict {
			fmt.Printf("rejected at offset %d: %s\n", off, reason)
			os.Exit(3)
		}
		rej[reason]++
	}
	for _, r := range recs {
		switch r.op {
		case 1:
			if _, ok := accts[uint32(r.a)]; ok {
				reject(r.off, "dup")
				continue
			}
			accts[uint32(r.a)] = &acct{id: uint32(r.a), name: r.name, bal: int64(r.b)}
		case 2:
			f, ok1 := accts[uint32(r.a)]
			t, ok2 := accts[uint32(r.b)]
			switch {
			case !ok1 || !ok2:
				reject(r.off, "unknown")
			case f.shut || t.shut:
				reject(r.off, "shut")
			case r.a == r.b:
				reject(r.off, "self")
			case int64(r.c) > f.bal:
				reject(r.off, "funds")
			default:
				f.bal -= int64(r.c)
				t.bal += int64(r.c)
			}
		case 3:
			a, ok := accts[uint32(r.a)]
			if !ok {
				reject(r.off, "unknown")
			} else if a.shut {
				reject(r.off, "shut")
			} else {
				a.shut = true
			}
		case 4:
			a, ok := accts[uint32(r.a)]
			if !ok {
				reject(r.off, "unknown")
			} else if a.shut {
				reject(r.off, "shut")
			} else {
				a.bal += int64(r.b)
			}
		}
	}
	var all []*acct
	open, shut := 0, 0
	var total int64
	for _, a := range accts {
		all = append(all, a)
		total += a.bal
		if a.shut {
			shut++
		} else {
			open++
		}
	}
	sort.Slice(all, func(i, j int) bool { return all[i].id < all[j].id })
	const M = 1000000007
	var g uint64
	for _, a := range all {
		g = (g*1000003 + uint64(a.id)*7 + uint64(a.bal)%M) % M
	}
	var op []*acct
	for _, a := range all {
		if !a.shut {
			op = append(op, a)
		}
	}
	sort.SliceStable(op, func(i, j int) bool { return op[i].bal > op[j].bal })
	fmt.Printf("records: %d\n", len(recs))
	fmt.Printf("accounts: %d open, %d shut\n", open, shut)
	fmt.Printf("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n", rej["dup"], rej["unknown"], rej["shut"], rej["self"], rej["funds"])
	fmt.Printf("total: %d\n", total)
	for i := 0; i < len(op) && i < 5; i++ {
		fmt.Printf("top: %d %s %d\n", op[i].id, op[i].name, op[i].bal)
	}
	fmt.Printf("digest: %d\n", g)
}
