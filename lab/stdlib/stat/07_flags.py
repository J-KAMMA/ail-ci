import stat


def main():
    print("UF_NODUMP", stat.UF_NODUMP)
    print("UF_IMMUTABLE", stat.UF_IMMUTABLE)
    print("UF_APPEND", stat.UF_APPEND)
    print("UF_OPAQUE", stat.UF_OPAQUE)
    print("UF_NOUNLINK", stat.UF_NOUNLINK)
    print("UF_COMPRESSED", stat.UF_COMPRESSED)
    print("UF_HIDDEN", stat.UF_HIDDEN)
    print("SF_ARCHIVED", stat.SF_ARCHIVED)
    print("SF_IMMUTABLE", stat.SF_IMMUTABLE)
    print("SF_APPEND", stat.SF_APPEND)
    print("SF_NOUNLINK", stat.SF_NOUNLINK)
    print("SF_SNAPSHOT", stat.SF_SNAPSHOT)
    user = (stat.UF_NODUMP | stat.UF_IMMUTABLE | stat.UF_APPEND |
            stat.UF_OPAQUE | stat.UF_NOUNLINK | stat.UF_COMPRESSED |
            stat.UF_HIDDEN)
    system = (stat.SF_ARCHIVED | stat.SF_IMMUTABLE | stat.SF_APPEND |
              stat.SF_NOUNLINK | stat.SF_SNAPSHOT)
    print("user flags", user)
    print("system flags", system)
    print("nodump set", user & stat.UF_NODUMP == stat.UF_NODUMP)
    print("snapshot set", system & stat.SF_SNAPSHOT == stat.SF_SNAPSHOT)
    print("append clear", user & stat.SF_APPEND == 0)
    print("attributes", stat.FILE_ATTRIBUTE_ARCHIVE, stat.FILE_ATTRIBUTE_DIRECTORY,
          stat.FILE_ATTRIBUTE_HIDDEN, stat.FILE_ATTRIBUTE_READONLY)
    print("done")


main()
