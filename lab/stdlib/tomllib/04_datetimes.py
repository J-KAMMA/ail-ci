import tomllib

DOC = '''
offset = 1979-05-27T07:32:00Z
offset_neg = 1979-05-27T00:32:00-07:00
local_dt = 1979-05-27T07:32:00
local_dt_frac = 1979-05-27T00:32:00.999999
local_date = 1979-05-27
local_time = 07:32:00
local_time_frac = 00:32:00.999999
'''


def main():
    data = tomllib.loads(DOC)
    for key in data:
        value = data[key]
        print(key, type(value).__name__, value.isoformat())
    print("offset type", type(data["offset"]).__name__)
    print("offset tz", data["offset"].utcoffset())
    print("neg tz", data["offset_neg"].utcoffset())
    print("date type", type(data["local_date"]).__name__)
    print("time type", type(data["local_time"]).__name__)
    print("frac micro", data["local_dt_frac"].microsecond)
    print("time micro", data["local_time_frac"].microsecond)


main()
