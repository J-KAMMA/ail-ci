# inventory_report

Category: records / structs

Read standard input, write standard output, exit with status 0.

Each input line is `name quantity unit_price` (integers). Model an item as a record with these fields. Print `name value` per item, where value = quantity * unit_price, ordered by value descending then name ascending. Finish with a line `total T` where T is the sum of all values.
