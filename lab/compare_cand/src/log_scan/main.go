package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
)

type parsed struct {
	ip     uint32
	hour   int
	status int
	nb     int64
	ps     int
	pe     int
}

type pent struct {
	count int64
	bytes int64
}

func two(s []byte, i, lo, hi int) (int, bool) {
	if i+2 > len(s) {
		return 0, false
	}
	a := int(s[i] - '0')
	b := int(s[i+1] - '0')
	if a < 0 || a > 9 || b < 0 || b > 9 {
		return 0, false
	}
	v := a*10 + b
	if v < lo || v > hi {
		return 0, false
	}
	return v, true
}

func monthOk(s []byte, i int) bool {
	if i+3 > len(s) {
		return false
	}
	v := uint32(s[i])<<16 | uint32(s[i+1])<<8 | uint32(s[i+2])
	switch v {
	case 0x4A616E, 0x466562, 0x4D6172, 0x417072, 0x4D6179, 0x4A756E,
		0x4A756C, 0x417567, 0x536570, 0x4F6374, 0x4E6F76, 0x446563:
		return true
	}
	return false
}

func methodOk(s []byte, a, b int) bool {
	n := b - a
	if n == 3 {
		if s[a] == 'G' && s[a+1] == 'E' && s[a+2] == 'T' {
			return true
		}
		return s[a] == 'P' && s[a+1] == 'U' && s[a+2] == 'T'
	}
	if n == 4 {
		return s[a] == 'P' && s[a+1] == 'O' && s[a+2] == 'S' && s[a+3] == 'T'
	}
	if n == 6 {
		return s[a] == 'D' && s[a+1] == 'E' && s[a+2] == 'L' &&
			s[a+3] == 'E' && s[a+4] == 'T' && s[a+5] == 'E'
	}
	return false
}

func pathOk(s []byte, a, b int) bool {
	n := b - a
	if n < 1 || n > 64 || s[a] != '/' {
		return false
	}
	for i := a; i < b; i++ {
		c := s[i]
		if (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') {
			continue
		}
		if c == '/' || c == '.' || c == '_' || c == '-' {
			continue
		}
		return false
	}
	return true
}

func parseLine(l []byte) (parsed, bool) {
	var p parsed
	n := len(l)
	i := 0
	var ip uint32
	for k := 0; k < 4; k++ {
		if k > 0 {
			if i >= n || l[i] != '.' {
				return p, false
			}
			i++
		}
		start := i
		var v uint32
		for i < n && i-start < 3 && l[i] >= '0' && l[i] <= '9' {
			v = v*10 + uint32(l[i]-'0')
			i++
		}
		if i == start || v > 255 {
			return p, false
		}
		ip = ip<<8 | v
	}
	if i+6 > n {
		return p, false
	}
	if !(l[i] == ' ' && l[i+1] == '-' && l[i+2] == ' ' && l[i+3] == '-' &&
		l[i+4] == ' ' && l[i+5] == '[') {
		return p, false
	}
	i += 6
	if _, ok := two(l, i, 1, 31); !ok {
		return p, false
	}
	i += 2
	if i >= n || l[i] != '/' {
		return p, false
	}
	i++
	if !monthOk(l, i) {
		return p, false
	}
	i += 3
	if i >= n || l[i] != '/' {
		return p, false
	}
	i++
	if i+4 > n {
		return p, false
	}
	for k := 0; k < 4; k++ {
		if l[i+k] < '0' || l[i+k] > '9' {
			return p, false
		}
	}
	i += 4
	if i >= n || l[i] != ':' {
		return p, false
	}
	i++
	hh, ok := two(l, i, 0, 23)
	if !ok {
		return p, false
	}
	i += 2
	if i >= n || l[i] != ':' {
		return p, false
	}
	i++
	if _, ok := two(l, i, 0, 59); !ok {
		return p, false
	}
	i += 2
	if i >= n || l[i] != ':' {
		return p, false
	}
	i++
	if _, ok := two(l, i, 0, 59); !ok {
		return p, false
	}
	i += 2
	if i+7 > n {
		return p, false
	}
	if !(l[i] == ' ' && l[i+1] == '+' && l[i+2] == '0' && l[i+3] == '0' &&
		l[i+4] == '0' && l[i+5] == '0' && l[i+6] == ']') {
		return p, false
	}
	i += 7
	if i >= n || l[i] != ' ' {
		return p, false
	}
	i++
	if i >= n || l[i] != '"' {
		return p, false
	}
	i++
	ms := i
	for i < n && l[i] != ' ' {
		i++
	}
	if i >= n || !methodOk(l, ms, i) {
		return p, false
	}
	i++
	ps := i
	for i < n && l[i] != ' ' {
		i++
	}
	if i >= n || !pathOk(l, ps, i) {
		return p, false
	}
	pe := i
	i++
	if i+8 > n {
		return p, false
	}
	if !(l[i] == 'H' && l[i+1] == 'T' && l[i+2] == 'T' && l[i+3] == 'P' &&
		l[i+4] == '/' && l[i+5] == '1' && l[i+6] == '.' && l[i+7] == '1') {
		return p, false
	}
	i += 8
	if i >= n || l[i] != '"' {
		return p, false
	}
	i++
	if i >= n || l[i] != ' ' {
		return p, false
	}
	i++
	if i+3 > n {
		return p, false
	}
	s0 := int(l[i] - '0')
	s1 := int(l[i+1] - '0')
	s2 := int(l[i+2] - '0')
	if s0 < 0 || s0 > 9 || s1 < 0 || s1 > 9 || s2 < 0 || s2 > 9 {
		return p, false
	}
	status := s0*100 + s1*10 + s2
	if status < 100 || status > 599 {
		return p, false
	}
	i += 3
	if i >= n || l[i] != ' ' {
		return p, false
	}
	i++
	if i >= n {
		return p, false
	}
	var nb int64
	if l[i] == '-' {
		if i+1 != n {
			return p, false
		}
	} else {
		if l[i] < '0' || l[i] > '9' {
			return p, false
		}
		for i < n {
			c := l[i]
			if c < '0' || c > '9' {
				return p, false
			}
			nb = nb*10 + int64(c-'0')
			if nb > 1000000000000 {
				return p, false
			}
			i++
		}
	}
	p.ip = ip
	p.hour = hh
	p.status = status
	p.nb = nb
	p.ps = ps
	p.pe = pe
	return p, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	if len(data) == 0 {
		w.WriteString("lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n")
		return
	}
	paths := make(map[string]*pent)
	ips := make(map[uint32]struct{})
	var scount [6]int64
	var hcount [24]int64
	var hbytes [24]int64
	var good, bad, total int64
	pos := 0
	for pos < len(data) {
		e := bytes.IndexByte(data[pos:], '\n')
		end := len(data)
		if e >= 0 {
			end = pos + e
		}
		line := data[pos:end]
		p, ok := parseLine(line)
		if ok {
			good++
			total += p.nb
			cls := p.status / 100
			if cls >= 2 && cls <= 5 {
				scount[cls]++
			}
			hcount[p.hour]++
			hbytes[p.hour] += p.nb
			key := string(line[p.ps:p.pe])
			ent, found := paths[key]
			if !found {
				ent = &pent{}
				paths[key] = ent
			}
			ent.count++
			ent.bytes += p.nb
			ips[p.ip] = struct{}{}
		} else {
			bad++
		}
		if end < len(data) {
			pos = end + 1
		} else {
			pos = len(data)
		}
	}
	fmt.Fprintf(w, "lines %d bad %d\n", good, bad)
	fmt.Fprintf(w, "status 2xx %d 3xx %d 4xx %d 5xx %d\n",
		scount[2], scount[3], scount[4], scount[5])
	fmt.Fprintf(w, "bytes %d\n", total)
	for h := 0; h < 24; h++ {
		if hcount[h] > 0 {
			fmt.Fprintf(w, "hour %02d %d %d\n", h, hcount[h], hbytes[h])
		}
	}
	keys := make([]string, 0, len(paths))
	for k := range paths {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		a, b := paths[keys[i]], paths[keys[j]]
		if a.count != b.count {
			return a.count > b.count
		}
		return keys[i] < keys[j]
	})
	m := len(keys)
	if m > 10 {
		m = 10
	}
	for _, k := range keys[:m] {
		e := paths[k]
		fmt.Fprintf(w, "path %s %d %d\n", k, e.count, e.bytes)
	}
	fmt.Fprintf(w, "ips %d\n", len(ips))
}
