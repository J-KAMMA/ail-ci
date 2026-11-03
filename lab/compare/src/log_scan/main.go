package main

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	statuses := make(map[string]int64)
	hours := make(map[int]int64)
	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, " ", 4)
		if len(parts) < 3 {
			continue
		}
		hour, _ := strconv.Atoi(parts[1][:2])
		statuses[parts[2]]++
		hours[hour]++
	}
	statusKeys := make([]string, 0, len(statuses))
	for status := range statuses {
		statusKeys = append(statusKeys, status)
	}
	sort.Strings(statusKeys)
	hourKeys := make([]int, 0, len(hours))
	for hour := range hours {
		hourKeys = append(hourKeys, hour)
	}
	sort.Ints(hourKeys)
	for _, status := range statusKeys {
		fmt.Printf("status %s %d\n", status, statuses[status])
	}
	for _, hour := range hourKeys {
		fmt.Printf("hour %02d %d\n", hour, hours[hour])
	}
}
