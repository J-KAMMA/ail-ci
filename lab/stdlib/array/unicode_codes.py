from array import array


def main():
    letters = array('u', 'hello')
    print(letters, len(letters), letters.tolist())
    print(letters[0], letters[-1], letters[1:4])
    letters.append('!')
    letters.insert(0, '>')
    print(letters.tounicode())
    print(letters.index('l'), letters.count('l'))
    letters.reverse()
    print(letters.tounicode())


main()
