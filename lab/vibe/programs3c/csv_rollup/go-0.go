package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

type group struct {
	region  string
	product string
	qty     int64
	revenue int64
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

func validQty(s string) (int64, bool) {
	body := s
	if strings.HasPrefix(s, "-") {
		body = s[1:]
	}
	if len(body) == 0 {
		return 0, false
	}
	for i := 0; i < len(body); i++ {
		if body[i] < '0' || body[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	if v < -1000 || v > 1000 {
		return 0, false
	}
	return v, true
}

func validPrice(s string) (int64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
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

	good, bad := 0, 0
	groups := map[[2]string]*group{}

	if len(s) > 0 {
		s = strings.TrimSuffix(s, "\n")
		for _, line := range strings.Split(s, "\n") {
			f := strings.Split(line, ",")
			if len(f) != 4 {
				bad++
				continue
			}
			if !validName(f[0]) || !validName(f[1]) {
				bad++
				continue
			}
			qty, ok := validQty(f[2])
			if !ok {
				bad++
				continue
			}
			price, ok2 := validPrice(f[3])
			if !ok2 {
				bad++
				continue
			}
			good++
			key := [2]string{f[0], f[1]}
			g := groups[key]
			if g == nil {
				g = &group{region: f[0], product: f[1]}
				groups[key] = g
			}
			g.qty += qty
			g.revenue += qty * price
		}
	}

	list := make([]*group, 0, len(groups))
	for _, g := range groups {
		list = append(list, g)
	}
	sort.Slice(list, func(i, j int) bool {
		a, b := list[i], list[j]
		if a.revenue != b.revenue {
			return a.revenue > b.revenue
		}
		if a.region != b.region {
			return a.region < b.region
		}
		return a.product < b.product
	})

	fmt.Fprintf(w, "rows %d bad %d groups %d\n", good, bad, len(groups))

	for i := 0; i < len(list) && i < 10; i++ {
		g := list[i]
		fmt.Fprintf(w, "%s %s %d %d\n", g.region, g.product, g.qty, g.revenue)
	}

	regions := map[string]int64{}
	var total int64
	for _, g := range list {
		regions[g.region] += g.revenue
		total += g.revenue
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
