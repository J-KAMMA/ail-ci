package main

import (
	"bufio"
	"fmt"
	"io"
	"math/big"
	"os"
	"strconv"
	"strings"
)

func validInt(s string) bool {
	if len(s) > 0 && s[0] == '-' {
		s = s[1:]
	}
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

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	var stack []int64
	stores := map[string]int64{}

	errf := func(ln int, reason string) {
		fmt.Fprintf(w, "error %d %s\n", ln, reason)
	}

	for i, raw := range lines {
		ln := i + 1
		line := strings.TrimSuffix(raw, "\r")
		line = strings.Trim(line, " \t")
		if line == "" || line[0] == '#' {
			continue
		}
		f := strings.Fields(line)
		cmd := f[0]
		args := f[1:]

		switch cmd {
		case "push":
			if len(args) != 1 {
				errf(ln, "cmd")
				continue
			}
			if !validInt(args[0]) {
				errf(ln, "int")
				continue
			}
			v, err := strconv.ParseInt(args[0], 10, 64)
			if err != nil {
				errf(ln, "int")
				continue
			}
			stack = append(stack, v)

		case "add", "sub", "mul":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 2 {
				errf(ln, "stack")
				continue
			}
			a := big.NewInt(stack[n-2])
			b := big.NewInt(stack[n-1])
			r := new(big.Int)
			switch cmd {
			case "add":
				r.Add(a, b)
			case "sub":
				r.Sub(a, b)
			case "mul":
				r.Mul(a, b)
			}
			if !r.IsInt64() {
				errf(ln, "overflow")
				continue
			}
			stack = stack[:n-2]
			stack = append(stack, r.Int64())

		case "dup":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				errf(ln, "stack")
				continue
			}
			stack = append(stack, stack[n-1])

		case "swap":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 2 {
				errf(ln, "stack")
				continue
			}
			stack[n-1], stack[n-2] = stack[n-2], stack[n-1]

		case "drop":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				errf(ln, "stack")
				continue
			}
			stack = stack[:n-1]

		case "store":
			if len(args) != 1 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				errf(ln, "stack")
				continue
			}
			stores[args[0]] = stack[n-1]
			stack = stack[:n-1]

		case "load":
			if len(args) != 1 {
				errf(ln, "cmd")
				continue
			}
			v, ok := stores[args[0]]
			if !ok {
				errf(ln, "var")
				continue
			}
			stack = append(stack, v)

		case "print":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				errf(ln, "stack")
				continue
			}
			fmt.Fprintf(w, "value %d\n", stack[n-1])

		case "clear":
			if len(args) != 0 {
				errf(ln, "cmd")
				continue
			}
			stack = nil

		default:
			errf(ln, "cmd")
		}
	}

	fmt.Fprintf(w, "stack %d\n", len(stack))
	if len(stack) > 0 {
		parts := make([]string, len(stack))
		for i, v := range stack {
			parts[i] = strconv.FormatInt(v, 10)
		}
		fmt.Fprintf(w, "%s\n", strings.Join(parts, " "))
	}
}
