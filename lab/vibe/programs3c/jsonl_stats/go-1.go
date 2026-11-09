package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
)

type tagAgg struct {
	count int64
	total int64
}

type userCount struct {
	name  string
	count int64
}

func parseRow(line []byte) (user string, amount int64, tag string, ok bool) {
	var obj map[string]json.RawMessage
	if err := json.Unmarshal(line, &obj); err != nil || obj == nil {
		return "", 0, "", false
	}

	uRaw, has := obj["user"]
	if !has {
		return "", 0, "", false
	}
	uRaw = bytes.TrimSpace(uRaw)
	if len(uRaw) == 0 || uRaw[0] != '"' {
		return "", 0, "", false
	}
	if err := json.Unmarshal(uRaw, &user); err != nil {
		return "", 0, "", false
	}

	aRaw, has := obj["amount"]
	if !has {
		return "", 0, "", false
	}
	aRaw = bytes.TrimSpace(aRaw)
	if len(aRaw) == 0 {
		return "", 0, "", false
	}
	c := aRaw[0]
	if c != '-' && !(c >= '0' && c <= '9') {
		return "", 0, "", false
	}
	amt, err := strconv.ParseInt(string(aRaw), 10, 64)
	if err != nil {
		return "", 0, "", false
	}
	amount = amt

	if tRaw, has := obj["tag"]; has {
		tRaw = bytes.TrimSpace(tRaw)
		if len(tRaw) == 0 || tRaw[0] != '"' {
			return "", 0, "", false
		}
		if err := json.Unmarshal(tRaw, &tag); err != nil {
			return "", 0, "", false
		}
	}

	return user, amount, tag, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := bytes.Split(data, []byte("\n"))

	bad := 0
	tags := map[string]*tagAgg{}
	users := map[string]int64{}

	for _, line := range lines {
		line = bytes.TrimSuffix(line, []byte("\r"))
		if len(bytes.Trim(line, " \t")) == 0 {
			continue
		}
		user, amount, tag, ok := parseRow(line)
		if !ok {
			bad++
			continue
		}
		t, exists := tags[tag]
		if !exists {
			t = &tagAgg{}
			tags[tag] = t
		}
		t.count++
		t.total += amount
		users[user]++
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	tagNames := make([]string, 0, len(tags))
	for name := range tags {
		tagNames = append(tagNames, name)
	}
	sort.Strings(tagNames)

	userList := make([]userCount, 0, len(users))
	for name, c := range users {
		userList = append(userList, userCount{name: name, count: c})
	}
	sort.Slice(userList, func(i, j int) bool {
		if userList[i].count != userList[j].count {
			return userList[i].count > userList[j].count
		}
		return userList[i].name < userList[j].name
	})

	fmt.Fprintf(w, "bad %d tags %d users %d\n", bad, len(tags), len(users))
	for _, name := range tagNames {
		t := tags[name]
		fmt.Fprintf(w, "tag %s count %d total %d\n", name, t.count, t.total)
	}
	limit := len(userList)
	if limit > 10 {
		limit = 10
	}
	for i := 0; i < limit; i++ {
		fmt.Fprintf(w, "user %s %d\n", userList[i].name, userList[i].count)
	}
}
