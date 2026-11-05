import mimetypes

mimetypes.init([])

for mtype in ("text/plain", "image/jpeg", "application/json", "text/html",
              "application/zip", "audio/mpeg", "application/x-tar",
              "image/svg+xml"):
    print(mtype, mimetypes.guess_extension(mtype))
    print(mtype, sorted(mimetypes.guess_all_extensions(mtype)))

for mtype in ("application/rtf", "image/webp", "audio/midi"):
    print(mtype, mimetypes.guess_extension(mtype, False),
          sorted(mimetypes.guess_all_extensions(mtype, False)))
