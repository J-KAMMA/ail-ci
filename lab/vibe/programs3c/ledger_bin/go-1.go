package main

import (
	"fmt"
	"os"
	"sort"
)

type parser struct {
	data []byte
	pos  int
}

func (p *parser) readVar() (uint64, string) {
	var val uint64
	n := 0
	for i := 0; ; i++ {
		if p.pos >= len(p.data) {
			return 0, "truncated"
		}
		b := p.data[p.pos]
		p.pos++
		if i == 4 && b&0x80 != 0 {
			return 0, "varint"
		}
		val |= uint64(b&0x7f) << (7 * uint(i))
		n = i + 1
		if b&0x80 == 0 {
			break
		}
	}
	if n >= 2 && p.data[p.pos-1] == 0 {
		return 0, "varint"
	}
	if val > 4294967295 {
		return 0, "varint"
	}
	return val, ""
}

type rec struct {
	off    int
	op     byte
	id     uint64
	to     uint64
	amount uint64
	name   string
}

func (p *parser) readRecord() (rec, string) {
	d := p.data
	start := p.pos
	r := rec{off: start}
	op := d[p.pos]
	p.pos++
	if op < 1 || op > 5 {
		return r, "opcode"
	}
	r.op = op
	var e string
	switch op {
	case 1:
		if r.id, e = p.readVar(); e != "" {
			return r, e
		}
		if p.pos >= len(d) {
			return r, "truncated"
		}
		nl := d[p.pos]
		p.pos++
		if nl < 1 || nl > 32 {
			return r, "name"
		}
		buf := make([]byte, 0, nl)
		for i := 0; i < int(nl); i++ {
			if p.pos >= len(d) {
				return r, "truncated"
			}
			b := d[p.pos]
			p.pos++
			if b < 0x21 || b > 0x7e {
				return r, "name"
			}
			buf = append(buf, b)
		}
		r.name = string(buf)
		if r.amount, e = p.readVar(); e != "" {
			return r, e
		}
	case 2:
		if r.id, e = p.readVar(); e != "" {
			return r, e
		}
		if r.to, e = p.readVar(); e != "" {
			return r, e
		}
		if r.amount, e = p.readVar(); e != "" {
			return r, e
		}
	case 3:
		if r.id, e = p.readVar(); e != "" {
			return r, e
		}
	case 4:
		if r.id, e = p.readVar(); e != "" {
			return r, e
		}
		if r.amount, e = p.readVar(); e != "" {
			return r, e
		}
	case 5:
		var l uint64
		if l, e = p.readVar(); e != "" {
			return r, e
		}
		if l > uint64(len(d)-p.pos) {
			return r, "truncated"
		}
		p.pos += int(l)
	}
	if p.pos >= len(d) {
		return r, "truncated"
	}
	c := 0
	for _, b := range d[start:p.pos] {
		c = (c*31 + int(b)) % 251
	}
	if int(d[p.pos]) != c {
		return r, "check"
	}
	p.pos++
	return r, ""
}

type acct struct {
	id   uint64
	name string
	bal  int64
	open bool
}

func main() {
	args := os.Args[1:]
	if len(args) != 1 {
		os.Exit(1)
	}
	data, err := os.ReadFile(args[0])
	if err != nil {
		os.Exit(1)
	}

	if len(data) < 6 || data[0] != 0xC7 || data[1] != 0x4C || data[2] != 0x58 || data[3] != 0x46 || data[4] != 2 || data[5]&^1 != 0 {
		fmt.Printf("error at offset 0: header\n")
		os.Exit(2)
	}
	strict := data[5]&1 == 1

	p := &parser{data: data, pos: 6}
	var recs []rec
	for p.pos < len(data) {
		r, e := p.readRecord()
		if e != "" {
			fmt.Printf("error at offset %d: %s\n", r.off, e)
			os.Exit(2)
		}
		recs = append(recs, r)
	}

	accts := map[uint64]*acct{}
	var dup, unk, shut, self, funds int
	reject := func(off int, reason string) {
		if strict {
			fmt.Printf("rejected at offset %d: %s\n", off, reason)
			os.Exit(3)
		}
		switch reason {
		case "dup":
			dup++
		case "unknown":
			unk++
		case "shut":
			shut++
		case "self":
			self++
		case "funds":
			funds++
		}
	}

	for _, r := range recs {
		switch r.op {
		case 1:
			if _, ok := accts[r.id]; ok {
				reject(r.off, "dup")
			} else {
				accts[r.id] = &acct{id: r.id, name: r.name, bal: int64(r.amount), open: true}
			}
		case 2:
			from := accts[r.id]
			to := accts[r.to]
			if from == nil || to == nil {
				reject(r.off, "unknown")
			} else if !from.open || !to.open {
				reject(r.off, "shut")
			} else if r.id == r.to {
				reject(r.off, "self")
			} else if int64(r.amount) > from.bal {
				reject(r.off, "funds")
			} else {
				amt := int64(r.amount)
				from.bal -= amt
				to.bal += amt
			}
		case 3:
			a := accts[r.id]
			if a == nil {
				reject(r.off, "unknown")
			} else if !a.open {
				reject(r.off, "shut")
			} else {
				a.open = false
			}
		case 4:
			a := accts[r.id]
			if a == nil {
				reject(r.off, "unknown")
			} else if !a.open {
				reject(r.off, "shut")
			} else {
				a.bal += int64(r.amount)
			}
		case 5:
		}
	}

	var openList []*acct
	var all []*acct
	nOpen, nShut := 0, 0
	var total int64
	for _, a := range accts {
		all = append(all, a)
		total += a.bal
		if a.open {
			nOpen++
			openList = append(openList, a)
		} else {
			nShut++
		}
	}

	sort.Slice(openList, func(i, j int) bool {
		if openList[i].bal != openList[j].bal {
			return openList[i].bal > openList[j].bal
		}
		return openList[i].id < openList[j].id
	})
	sort.Slice(all, func(i, j int) bool {
		return all[i].id < all[j].id
	})

	const mod = 1000000007
	var g int64
	for _, a := range all {
		g = (g*1000003 + int64(a.id)*7 + a.bal) % mod
	}

	fmt.Printf("records: %d\n", len(recs))
	fmt.Printf("accounts: %d open, %d shut\n", nOpen, nShut)
	fmt.Printf("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n", dup, unk, shut, self, funds)
	fmt.Printf("total: %d\n", total)
	for i := 0; i < len(openList) && i < 5; i++ {
		a := openList[i]
		fmt.Printf("top: %d %s %d\n", a.id, a.name, a.bal)
	}
	fmt.Printf("digest: %d\n", g)
	os.Exit(0)
}
