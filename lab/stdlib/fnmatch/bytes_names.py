import fnmatch


def main():
    names = [b"photo.jpg", b"photo.png", b"notes.txt", b"IMG_001.JPG", b""]
    print("jpg", fnmatch.filter(names, b"*.jpg"))
    print("all", fnmatch.filter(names, b"*"))
    print("empty", fnmatch.filter(names, b""))
    for name in names:
        print(name, fnmatch.fnmatchcase(name, b"*.JPG"), fnmatch.fnmatch(name, b"*.jpg"))
    pattern = b"photo.??? "
    print("translate bytes", fnmatch.fnmatchcase(b"photo.jpg", pattern.strip()))
    print("question", fnmatch.fnmatchcase(b"photo.jpg", b"photo.???"))
    print("class", fnmatch.fnmatchcase(b"photo.png", b"photo.[jp]*"))
    print("literal", fnmatch.fnmatchcase(b"photo.jpg", b"photo.jpg"))


main()
