package main

import (
	"bufio"
	"math"
	"os"
	"strconv"
	"strings"
)

func parse(s string) (uint64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseUint(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func upd(l, r, c float64) float64 {
	d := float64(l+r) - float64(c+c)
	g := d / float64(1.0+math.Sqrt(float64(float64(d*d)+0.0625)))
	return c + float64(0.375*g)
}

func fmtv(v float64) string {
	s := strconv.FormatFloat(v, 'f', 9, 64)
	if strings.HasPrefix(s, "-") && strings.Trim(s[1:], "0.") == "" {
		return s[1:]
	}
	return s
}

func main() {
	if len(os.Args) != 4 {
		os.Exit(1)
	}
	n64, ok1 := parse(os.Args[1])
	t64, ok2 := parse(os.Args[2])
	seed, ok3 := parse(os.Args[3])
	if !ok1 || !ok2 || !ok3 || n64 < 1 || n64 > 10000000 || t64 > 1000000 {
		os.Exit(1)
	}
	n := int(n64)
	t := int(t64)
	h := make([]float64, n)
	x := seed
	for i := 0; i < n; i++ {
		x = x*6364136223846793005 + 1442695040888963407
		h[i] = float64(int64((x>>33)%2001)-1000) / 64.0
	}
	for s := 1; s <= t; s++ {
		if s&1 == 1 {
			h[0] = upd(h[n-1], h[(1)%n], h[0])
			if n > 1 {
				prev := h[0]
				for i := 1; i < n-1; i++ {
					prev = upd(prev, h[i+1], h[i])
					h[i] = prev
				}
				h[n-1] = upd(prev, h[0], h[n-1])
			}
		} else {
			last := n - 1
			h[last] = upd(h[(last+n-1)%n], h[0], h[last])
			if n > 1 {
				next := h[last]
				for i := n - 2; i >= 1; i-- {
					next = upd(h[i-1], next, h[i])
					h[i] = next
				}
				h[0] = upd(h[n-1], next, h[0])
			}
		}
	}
	var sum, energy float64
	mn, mx := h[0], h[0]
	for i := 0; i < n; i++ {
		sum = sum + h[i]
		tt := h[(i+1)%n] - h[i]
		energy = energy + float64(tt*tt)
		if h[i] < mn {
			mn = h[i]
		}
		if h[i] > mx {
			mx = h[i]
		}
	}
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	w.WriteString("sum " + fmtv(sum) + "\n")
	w.WriteString("energy " + fmtv(energy) + "\n")
	w.WriteString("min " + fmtv(mn) + "\n")
	w.WriteString("max " + fmtv(mx) + "\n")
	w.WriteString("first " + fmtv(h[0]) + "\n")
	w.WriteString("middle " + fmtv(h[n/2]) + "\n")
	w.WriteString("last " + fmtv(h[n-1]) + "\n")
}
