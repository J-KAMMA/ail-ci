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

func parseInt64(s string) (int64, bool) {
	t := s
	if strings.HasPrefix(t, "-") {
		t = t[1:]
	}
	if len(t) == 0 {
		return 0, false
	}
	for i := 0; i < len(t); i++ {
		if t[i] < '0' || t[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	lines := strings.Split(string(data), "\n")
	var stack []int64
	vars := map[string]int64{}

	for idx, raw := range lines {
		lineNo := idx + 1
		line := strings.TrimSuffix(raw, "\r")
		line = strings.Trim(line, " \t")
		if line == "" || line[0] == '#' {
			continue
		}
		f := strings.Fields(line)
		cmd := f[0]
		args := f[1:]

		fail := func(reason string) {
			fmt.Fprintf(out, "error %d %s\n", lineNo, reason)
		}

		switch cmd {
		case "push":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			v, ok := parseInt64(args[0])
			if !ok {
				fail("int")
				continue
			}
			stack = append(stack, v)

		case "add", "sub", "mul":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 2 {
				fail("stack")
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
				fail("overflow")
				continue
			}
			stack = stack[:n-2]
			stack = append(stack, r.Int64())

		case "dup":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				fail("stack")
				continue
			}
			stack = append(stack, stack[n-1])

		case "swap":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 2 {
				fail("stack")
				continue
			}
			stack[n-1], stack[n-2] = stack[n-2], stack[n-1]

		case "drop":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				fail("stack")
				continue
			}
			stack = stack[:n-1]

		case "store":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				fail("stack")
				continue
			}
			vars[args[0]] = stack[n-1]
			stack = stack[:n-1]

		case "load":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			v, ok := vars[args[0]]
			if !ok {
				fail("var")
				continue
			}
			stack = append(stack, v)

		case "print":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			n := len(stack)
			if n < 1 {
				fail("stack")
				continue
			}
			fmt.Fprintf(out, "value %d\n", stack[n-1])

		case "clear":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			stack = stack[:0]

		default:
			fail("cmd")
		}
	}

	fmt.Fprintf(out, "stack %d\n", len(stack))
	if len(stack) > 0 {
		parts := make([]string, len(stack))
		for i, v := range stack {
			parts[i] = strconv.FormatInt(v, 10)
		}
		out.WriteString(strings.Join(parts, " ") + "\n")
	}
}
