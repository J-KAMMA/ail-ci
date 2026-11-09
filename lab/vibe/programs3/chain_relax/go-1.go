package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"strconv"
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

func fmtVal(v float64) string {
	s := strconv.FormatFloat(v, 'f', 9, 64)
	if s == "-0.000000000" {
		return "0.000000000"
	}
	return s
}

func main() {
	if len(os.Args) != 4 {
		os.Exit(1)
	}
	args := os.Args[1:]
	for _, a := range args {
		if !isDigits(a) {
			os.Exit(1)
		}
	}

	n64, err := strconv.ParseUint(args[0], 10, 64)
	if err != nil {
		os.Exit(1)
	}
	t64, err := strconv.ParseUint(args[1], 10, 64)
	if err != nil {
		os.Exit(1)
	}
	seed, err := strconv.ParseUint(args[2], 10, 64)
	if err != nil {
		os.Exit(1)
	}
	if n64 < 1 || n64 > 10000000 {
		os.Exit(1)
	}
	if t64 > 1000000 {
		os.Exit(1)
	}

	n := int(n64)
	T := int(t64)
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
				li := i - 1
				if li < 0 {
					li = n - 1
				}
				ri := i + 1
				if ri >= n {
					ri = 0
				}
				c := h[i]
				l := h[li]
				r := h[ri]
				d := (l + r) - (c + c)
				dd := d * d
				root := math.Sqrt(dd + 0.0625)
				g := d / (1.0 + root)
				prod := 0.375 * g
				h[i] = c + prod
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
				l := h[li]
				r := h[ri]
				d := (l + r) - (c + c)
				dd := d * d
				root := math.Sqrt(dd + 0.0625)
				g := d / (1.0 + root)
				prod := 0.375 * g
				h[i] = c + prod
			}
		}
	}

	sum := 0.0
	energy := 0.0
	mn := h[0]
	mx := h[0]
	for i := 0; i < n; i++ {
		hi := h[i]
		sum = sum + hi
		ni := i + 1
		if ni >= n {
			ni = 0
		}
		t := h[ni] - hi
		energy = energy + t*t
		if hi < mn {
			mn = hi
		}
		if hi > mx {
			mx = hi
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	emit := func(label string, v float64) {
		fmt.Fprintf(w, "%s %s\n", label, fmtVal(v))
	}

	emit("sum", sum)
	emit("energy", energy)
	emit("min", mn)
	emit("max", mx)
	emit("first", h[0])
	emit("middle", h[n/2])
	emit("last", h[n-1])
}
