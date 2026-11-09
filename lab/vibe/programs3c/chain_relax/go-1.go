package main

import (
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

func parseDigits(s string, max uint64) (uint64, bool) {
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
	if v > max {
		return 0, false
	}
	return v, true
}

func fmtVal(v float64) string {
	s := fmt.Sprintf("%.9f", v)
	if len(s) > 0 && s[0] == '-' {
		if strings.Trim(s[1:], "0.") == "" {
			s = s[1:]
		}
	}
	return s
}

func update(h []float64, n, i int) {
	li := i - 1
	if li < 0 {
		li = n - 1
	}
	ri := i + 1
	if ri == n {
		ri = 0
	}
	l := h[li]
	r := h[ri]
	c := h[i]
	d := (l + r) - (c + c)
	dd := float64(d*d) + 0.0625
	g := d / (1.0 + math.Sqrt(dd))
	h[i] = c + float64(0.375*g)
}

func main() {
	if len(os.Args) != 4 {
		os.Exit(1)
	}
	nu, ok1 := parseDigits(os.Args[1], 10000000)
	tu, ok2 := parseDigits(os.Args[2], 1000000)
	seed, ok3 := parseDigits(os.Args[3], math.MaxUint64)
	if !ok1 || !ok2 || !ok3 || nu < 1 {
		os.Exit(1)
	}
	n := int(nu)
	T := int(tu)

	h := make([]float64, n)
	x := seed
	for i := 0; i < n; i++ {
		x = x*6364136223846793005 + 1442695040888963407
		v := int64((x>>33)%2001) - 1000
		h[i] = float64(v) / 64.0
	}

	for s := 1; s <= T; s++ {
		if s%2 == 1 {
			for i := 0; i < n; i++ {
				update(h, n, i)
			}
		} else {
			for i := n - 1; i >= 0; i-- {
				update(h, n, i)
			}
		}
	}

	sum := 0.0
	energy := 0.0
	mn := h[0]
	mx := h[0]
	for i := 0; i < n; i++ {
		sum = sum + h[i]
		ni := i + 1
		if ni == n {
			ni = 0
		}
		t := h[ni] - h[i]
		energy = energy + float64(t*t)
		if h[i] < mn {
			mn = h[i]
		}
		if h[i] > mx {
			mx = h[i]
		}
	}

	var sb strings.Builder
	sb.WriteString("sum " + fmtVal(sum) + "\n")
	sb.WriteString("energy " + fmtVal(energy) + "\n")
	sb.WriteString("min " + fmtVal(mn) + "\n")
	sb.WriteString("max " + fmtVal(mx) + "\n")
	sb.WriteString("first " + fmtVal(h[0]) + "\n")
	sb.WriteString("middle " + fmtVal(h[n/2]) + "\n")
	sb.WriteString("last " + fmtVal(h[n-1]) + "\n")
	os.Stdout.WriteString(sb.String())
	os.Exit(0)
}
