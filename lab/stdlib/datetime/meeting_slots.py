from datetime import datetime, timedelta, timezone


def main() -> None:
    utc = timezone.utc
    ist = timezone(timedelta(hours=5, minutes=30), "IST")
    jst = timezone(timedelta(hours=9), "JST")
    west = timezone(timedelta(hours=-8))
    standup = datetime(2024, 5, 6, 9, 0, tzinfo=ist)
    review = datetime(2024, 5, 6, 4, 30, tzinfo=utc)
    demo = datetime(2024, 5, 6, 13, 30, tzinfo=jst)
    print("standup", standup.isoformat(), standup.strftime("%Y-%m-%d %H:%M %z %Z"),
          standup.utcoffset(), standup.tzname())
    print("review", review.isoformat(), review.astimezone(ist), review.astimezone(west))
    print("demo", demo.isoformat(), demo.astimezone(utc), demo.utcoffset())
    print("same", standup == review, review < demo, demo > standup)
    slots = [standup, review, demo]
    slots.sort()
    for slot in slots:
        print(slot.astimezone(utc).strftime("%H:%M"), slot.tzname())
    length = timedelta(minutes=45)
    for slot in slots:
        print(slot.isoformat(timespec="minutes"), "ends", (slot + length).astimezone(utc).strftime("%H:%M"))
    naive = standup.replace(tzinfo=None)
    print("naive", naive, naive.tzinfo is None, standup.tzinfo is not None)


main()
