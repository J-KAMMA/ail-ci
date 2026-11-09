package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

type key struct {
	r, p string
}

type group struct {
	r, p string
	qty  int64
	rev  int64
}

func validName(s string) bool {
	if len(s) < 1 || len(s) > 16 {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_') {
			return false
		}
	}
	return true
}

// parseDigits parses a non-empty string of ASCII digits. Values above
// 1e12 are clamped (they are out of range for every field anyway).
func parseDigits(s string) (int64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	var v int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		if v <= 1000000000000 {
			v = v*10 + int64(c-'0')
		}
	}
	return v, true
}

func parseQty(s string) (int64, bool) {
	neg := false
	if len(s) > 0 && s[0] == '-' {
		neg = true
		s = s[1:]
	}
	v, ok := parseDigits(s)
	if !ok {
		return 0, false
	}
	if neg {
		v = -v
	}
	if v < -1000 || v > 1000 {
		return 0, false
	}
	return v, true
}

func parsePrice(s string) (int64, bool) {
	v, ok := parseDigits(s)
	if !ok {
		return 0, false
	}
	if v < 0 || v > 10000000 {
		return 0, false
	}
	return v, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	if len(data) == 0 {
		fmt.Fprint(w, "rows 0 bad 0 groups 0\ntotal 0\n")
		return
	}

	s := string(data)
	idx := strings.IndexByte(s, '\n')
	if idx < 0 {
		s = ""
	} else {
		s = s[idx+1:]
	}

	var lines []string
	if s != "" {
		if strings.HasSuffix(s, "\n") {
			s = s[:len(s)-1]
		}
		lines = strings.Split(s, "\n")
	}

	groups := make(map[key]*group)
	regions := make(map[string]int64)
	good, bad := 0, 0

	for _, line := range lines {
		fields := strings.Split(line, ",")
		if len(fields) != 4 {
			bad++
			continue
		}
		region, product, qs, ps := fields[0], fields[1], fields[2], fields[3]
		if !validName(region) || !validName(product) {
			bad++
			continue
		}
		qty, ok := parseQty(qs)
		if !ok {
			bad++
			continue
		}
		price, ok := parsePrice(ps)
		if !ok {
			bad++
			continue
		}
		good++
		k := key{region, product}
		g, exists := groups[k]
		if !exists {
			g = &group{r: region, p: product}
			groups[k] = g
		}
		g.qty += qty
		g.rev += qty * price
	}

	gs := make([]*group, 0, len(groups))
	var total int64
	for _, g := range groups {
		gs = append(gs, g)
		total += g.rev
		regions[g.r] += g.rev
	}

	sort.Slice(gs, func(i, j int) bool {
		a, b := gs[i], gs[j]
		if a.rev != b.rev {
			return a.rev > b.rev
		}
		if a.r != b.r {
			return a.r < b.r
		}
		return a.p < b.p
	})

	fmt.Fprintf(w, "rows %d bad %d groups %d\n", good, bad, len(gs))

	top := len(gs)
	if top > 10 {
		top = 10
	}
	for i := 0; i < top; i++ {
		g := gs[i]
		fmt.Fprintf(w, "%s %s %d %d\n", g.r, g.p, g.qty, g.rev)
	}

	names := make([]string, 0, len(regions))
	for r := range regions {
		names = append(names, r)
	}
	sort.Strings(names)
	for _, r := range names {
		fmt.Fprintf(w, "region %s revenue %d\n", r, regions[r])
	}

	fmt.Fprintf(w, "total %d\n", total)
}
