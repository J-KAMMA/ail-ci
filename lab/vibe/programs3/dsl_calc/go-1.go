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

func parsePushArg(s string) (int64, bool) {
	if s == "" {
		return 0, false
	}

	start := 0
	if s[0] == '-' {
		if len(s) == 1 {
			return 0, false
		}
		start = 1
	}

	for i := start; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
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
	lines := strings.Split(string(data), "\n")

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	stack := make([]int64, 0)
	stores := make(map[string]int64)

	for i, raw := range lines {
		lineNo := i + 1

		line := strings.TrimSuffix(raw, "\r")
		line = strings.Trim(line, " \t")

		if line == "" || line[0] == '#' {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}

		cmd := fields[0]
		args := fields[1:]

		fail := func(reason string) {
			fmt.Fprintf(out, "error %d %s\n", lineNo, reason)
		}

		switch cmd {
		case "push":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			v, ok := parsePushArg(args[0])
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
			if len(stack) < 2 {
				fail("stack")
				continue
			}

			a := stack[len(stack)-2]
			b := stack[len(stack)-1]

			var result *big.Int
			switch cmd {
			case "add":
				result = new(big.Int).Add(big.NewInt(a), big.NewInt(b))
			case "sub":
				result = new(big.Int).Sub(big.NewInt(a), big.NewInt(b))
			case "mul":
				result = new(big.Int).Mul(big.NewInt(a), big.NewInt(b))
			}

			if !result.IsInt64() {
				fail("overflow")
				continue
			}

			stack = stack[:len(stack)-2]
			stack = append(stack, result.Int64())

		case "dup":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			if len(stack) < 1 {
				fail("stack")
				continue
			}
			stack = append(stack, stack[len(stack)-1])

		case "swap":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			if len(stack) < 2 {
				fail("stack")
				continue
			}
			n := len(stack)
			stack[n-1], stack[n-2] = stack[n-2], stack[n-1]

		case "drop":
			if len(args) != 0 {
				fail("cmd")
				continue
			}
			if len(stack) < 1 {
				fail("stack")
				continue
			}
			stack = stack[:len(stack)-1]

		case "store":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			if len(stack) < 1 {
				fail("stack")
				continue
			}
			stores[args[0]] = stack[len(stack)-1]
			stack = stack[:len(stack)-1]

		case "load":
			if len(args) != 1 {
				fail("cmd")
				continue
			}
			v, ok := stores[args[0]]
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
			if len(stack) < 1 {
				fail("stack")
				continue
			}
			fmt.Fprintf(out, "value %d\n", stack[len(stack)-1])

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
		for i, v := range stack {
			if i > 0 {
				fmt.Fprint(out, " ")
			}
			fmt.Fprintf(out, "%d", v)
		}
		fmt.Fprint(out, "\n")
	}
}
