import mimetypes

mimetypes.init([])

for name in ("report.tar.gz", "report.tgz", "report.taz", "report.tz",
             "backup.tar.bz2", "backup.tbz2", "logs.tar.xz", "logs.txz",
             "data.gz", "data.Z", "data.bz2", "data.xz", "data.br"):
    print(name, mimetypes.guess_type(name))
