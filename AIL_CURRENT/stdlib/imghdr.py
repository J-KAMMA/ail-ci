"""Recognize image file formats based on their first few bytes.

Derived from CPython 3.12 Lib/imghdr.py; PSF License, see stdlib/LICENSE-PSF.txt.

This is CPython 3.12's Lib/imghdr.py as AIL source.  `what`, every `test_*` function, their order in
`tests` and the returned strings are CPython's.

Differences from CPython, all forced by this compiler:

* `from os import PathLike` is refused (`os.PathLike used here is not built`), so `what` accepts
  only `str` paths here.  Passing a `pathlib.Path` to `what` stops loudly instead of working.
* `warnings._deprecated(__name__, remove=(3, 13))` is dropped, so `import imghdr` prints no
  `DeprecationWarning` on stderr.  CPython 3.12 prints one; stdout and the exit status are the
  same in both, which is what the tests compare.
* The `test()`/`testall()` command-line helper at the bottom of CPython's file is dropped.  The
  compiler refuses `except KeyboardInterrupt` and `os.path.isdir`/`os.path.join`; the helpers are
  not part of the public API (`__all__ == ["what"]`) and no caller reaches them by importing.

`ord(b'P')` is written as `b'P'[0]` because this compiler's `ord()` does not accept a bytes
argument (it builds on the general path and stops at runtime).
"""

__all__ = ["what"]


#-------------------------#
# Recognize image headers #
#-------------------------#

def what(file, h=None):
    """Return the type of image contained in a file or byte stream."""
    f = None
    try:
        if h is None:
            if isinstance(file, str):
                f = open(file, 'rb')
                h = f.read(32)
            else:
                location = file.tell()
                h = file.read(32)
                file.seek(location)
        for tf in tests:
            res = tf(h, f)
            if res:
                return res
    finally:
        if f:
            f.close()
    return None


#---------------------------------#
# Subroutines per image file type #
#---------------------------------#

tests = []


def test_jpeg(h, f):
    """Test for JPEG data with JFIF or Exif markers; and raw JPEG."""
    if h[6:10] in (b'JFIF', b'Exif'):
        return 'jpeg'
    elif h[:4] == b'\xff\xd8\xff\xdb':
        return 'jpeg'


tests.append(test_jpeg)


def test_png(h, f):
    """Verify if the image is a PNG."""
    if h.startswith(b'\211PNG\r\n\032\n'):
        return 'png'


tests.append(test_png)


def test_gif(h, f):
    """Verify if the image is a GIF ('87 or '89 variants)."""
    if h[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'


tests.append(test_gif)


def test_tiff(h, f):
    """Verify if the image is a TIFF (can be in Motorola or Intel byte order)."""
    if h[:2] in (b'MM', b'II'):
        return 'tiff'


tests.append(test_tiff)


def test_rgb(h, f):
    """test for the SGI image library."""
    if h.startswith(b'\001\332'):
        return 'rgb'


tests.append(test_rgb)


def test_pbm(h, f):
    """Verify if the image is a PBM (portable bitmap)."""
    if len(h) >= 3 and \
        h[0] == b'P'[0] and h[1] in b'14' and h[2] in b' \t\n\r':
        return 'pbm'


tests.append(test_pbm)


def test_pgm(h, f):
    """Verify if the image is a PGM (portable graymap)."""
    if len(h) >= 3 and \
        h[0] == b'P'[0] and h[1] in b'25' and h[2] in b' \t\n\r':
        return 'pgm'


tests.append(test_pgm)


def test_ppm(h, f):
    """Verify if the image is a PPM (portable pixmap)."""
    if len(h) >= 3 and \
        h[0] == b'P'[0] and h[1] in b'36' and h[2] in b' \t\n\r':
        return 'ppm'


tests.append(test_ppm)


def test_rast(h, f):
    """test for the Sun raster file."""
    if h.startswith(b'\x59\xA6\x6A\x95'):
        return 'rast'


tests.append(test_rast)


def test_xbm(h, f):
    """Verify if the image is a X bitmap (X10 or X11)."""
    if h.startswith(b'#define '):
        return 'xbm'


tests.append(test_xbm)


def test_bmp(h, f):
    """Verify if the image is a BMP file."""
    if h.startswith(b'BM'):
        return 'bmp'


tests.append(test_bmp)


def test_webp(h, f):
    """Verify if the image is a WebP."""
    if h.startswith(b'RIFF') and h[8:12] == b'WEBP':
        return 'webp'


tests.append(test_webp)


def test_exr(h, f):
    """verify is the image ia a OpenEXR fileOpenEXR."""
    if h.startswith(b'\x76\x2f\x31\x01'):
        return 'exr'


tests.append(test_exr)
