package main

import (
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

func isDigits(s string) bool {
	if len(s) == 0 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func parseBounded(s string, max uint64) (uint64, bool) {
	if !isDigits(s) {
		return 0, false
	}
	v, err := strconv.ParseUint(s, 10, 64)
	if err != nil || v > max {
		return 0, false
	}
	return v, true
}

func fmtFixed(v float64) string {
	s := strconv.FormatFloat(v, 'f', 9, 64)
	if strings.Trim(s, "-0.") == "" {
		return "0.000000000"
	}
	return s
}

func main() {
	args := os.Args[1:]
	if len(args) != 3 {
		os.Exit(1)
	}
	nu, ok1 := parseBounded(args[0], 10000000)
	tu, ok2 := parseBounded(args[1], 1000000)
	if !isDigits(args[2]) {
		os.Exit(1)
	}
	seed, err := strconv.ParseUint(args[2], 10, 64)
	if !ok1 || !ok2 || err != nil {
		os.Exit(1)
	}
	if nu < 1 {
		os.Exit(1)
	}
	n := int(nu)
	T := int(tu)

	h := make([]float64, n)
	x := seed
	for i := 0; i < n; i++ {
		x = x*6364136223846793005 + 1442695040888963407
		h[i] = float64(int64((x>>33)%2001)-1000) / 64.0
	}

	for s := 1; s <= T; s++ {
		if s%2 == 1 {
			for i := 0; i < n; i++ {
				li := i - 1
				if li < 0 {
					li = n - 1
				}
				ri := i + 1
				if ri >= n {
					ri = 0
				}
				c := h[i]
				d := (h[li] + h[ri]) - (c + c)
				dd := float64(d * d)
				root := math.Sqrt(dd + 0.0625)
				g := d / (1.0 + root)
				h[i] = c + float64(0.375*g)
			}
		} else {
			for i := n - 1; i >= 0; i-- {
				li := i - 1
				if li < 0 {
					li = n - 1
				}
				ri := i + 1
				if ri >= n {
					ri = 0
				}
				c := h[i]
				d := (h[li] + h[ri]) - (c + c)
				dd := float64(d * d)
				root := math.Sqrt(dd + 0.0625)
				g := d / (1.0 + root)
				h[i] = c + float64(0.375*g)
			}
		}
	}

	sum := 0.0
	energy := 0.0
	mn := h[0]
	mx := h[0]
	for i := 0; i < n; i++ {
		sum = sum + h[i]
		ri := i + 1
		if ri >= n {
			ri = 0
		}
		t := h[ri] - h[i]
		energy = energy + float64(t*t)
		if h[i] < mn {
			mn = h[i]
		}
		if h[i] > mx {
			mx = h[i]
		}
	}

	fmt.Printf("sum %s\n", fmtFixed(sum))
	fmt.Printf("energy %s\n", fmtFixed(energy))
	fmt.Printf("min %s\n", fmtFixed(mn))
	fmt.Printf("max %s\n", fmtFixed(mx))
	fmt.Printf("first %s\n", fmtFixed(h[0]))
	fmt.Printf("middle %s\n", fmtFixed(h[n/2]))
	fmt.Printf("last %s\n", fmtFixed(h[n-1]))
	os.Exit(0)
}
