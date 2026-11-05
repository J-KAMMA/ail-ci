import mimetypes

mimetypes.init([])

print("before", mimetypes.guess_type("sample.ailx"), mimetypes.guess_type("other.zzz"))

mimetypes.add_type("application/x-ail", ".ail")
mimetypes.add_type("text/x-note", ".note")
print("after", mimetypes.guess_type("sample.ail"), mimetypes.guess_type("sample.note"))
print("ext", mimetypes.guess_extension("application/x-ail"))

db = mimetypes.MimeTypes()
print("instance", db.guess_type("mine.ail"), db.guess_type("page.html"))
print("sizes", len(db.types_map[True]), len(db.types_map[False]))
print("entries", db.types_map[True][".txt"], db.types_map[True][".json"])
db.add_type("application/x-mine", ".mine")
print("added", db.guess_type("file.mine"), db.guess_extension("application/x-mine"))
print("module still", mimetypes.guess_type("file.mine"))
print("strict flat", mimetypes.types_map[".txt"], mimetypes.types_map[".svg"])
