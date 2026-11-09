package main

import (
	"fmt"
	"math"
	"os"
	"strconv"
)

func parseArg(s string, min, max uint64) (uint64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseUint(s, 10, 64)
	if err != nil || v < min || v > max {
		return 0, false
	}
	return v, true
}

func relax(h []float64, i, li, ri int) {
	l := h[li]
	r := h[ri]
	c := h[i]
	d := (l + r) - (c + c)
	g := d / (1.0 + math.Sqrt(d*d+0.0625))
	h[i] = c + 0.375*g
}

func printValue(name string, v float64) {
	s := strconv.FormatFloat(v, 'f', 9, 64)
	if s == "-0.000000000" {
		s = "0.000000000"
	}
	fmt.Printf("%s %s\n", name, s)
}

func main() {
	if len(os.Args) != 4 {
		os.Exit(1)
	}

	n64, ok := parseArg(os.Args[1], 1, 10000000)
	if !ok {
		os.Exit(1)
	}
	t64, ok := parseArg(os.Args[2], 0, 1000000)
	if !ok {
		os.Exit(1)
	}
	seed, ok := parseArg(os.Args[3], 0, ^uint64(0))
	if !ok {
		os.Exit(1)
	}

	n := int(n64)
	sweeps := int(t64)
	h := make([]float64, n)

	x := seed
	for i := 0; i < n; i++ {
		x = x*6364136223846793005 + 1442695040888963407
		v := int64((x>>33)%2001) - 1000
		h[i] = float64(v) / 64.0
	}

	if n > 1 {
		for s := 1; s <= sweeps; s++ {
			if s&1 != 0 {
				relax(h, 0, n-1, 1)
				for i := 1; i < n-1; i++ {
					relax(h, i, i-1, i+1)
				}
				relax(h, n-1, n-2, 0)
			} else {
				relax(h, n-1, n-2, 0)
				for i := n - 2; i >= 1; i-- {
					relax(h, i, i-1, i+1)
				}
				relax(h, 0, n-1, 1)
			}
		}
	}

	sum := 0.0
	energy := 0.0
	minv := h[0]
	maxv := h[0]

	for i := 0; i < n; i++ {
		hi := h[i]
		sum = sum + hi

		j := i + 1
		if j == n {
			j = 0
		}
		t := h[j] - hi
		energy = energy + t*t

		if hi < minv {
			minv = hi
		}
		if hi > maxv {
			maxv = hi
		}
	}

	printValue("sum", sum)
	printValue("energy", energy)
	printValue("min", minv)
	printValue("max", maxv)
	printValue("first", h[0])
	printValue("middle", h[n/2])
	printValue("last", h[n-1])
}
