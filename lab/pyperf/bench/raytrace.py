"""Raytracer: three spheres lit by a point light, rendered without an image.

Each pixel shoots one ray, finds the nearest sphere, and adds a Lambert plus
Phong term to three channel accumulators.  Vector and Sphere keep the vector
arithmetic in classes; the final colour sums are printed with nine decimals.
"""
import sys
import math


class Vector:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def plus(self, o):
        return Vector(self.x + o.x, self.y + o.y, self.z + o.z)

    def minus(self, o):
        return Vector(self.x - o.x, self.y - o.y, self.z - o.z)

    def times(self, s):
        return Vector(self.x * s, self.y * s, self.z * s)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z

    def norm(self):
        return math.sqrt(self.dot(self))

    def unit(self):
        d = self.norm()
        return Vector(self.x / d, self.y / d, self.z / d)


class Sphere:
    def __init__(self, centre, radius, colour):
        self.centre = centre
        self.radius = radius
        self.colour = colour

    def hit(self, origin, direction):
        oc = origin.minus(self.centre)
        b = oc.dot(direction)
        c = oc.dot(oc) - self.radius * self.radius
        disc = b * b - c
        if disc < 0.0:
            return -1.0
        root = math.sqrt(disc)
        t = -b - root
        if t > 0.001:
            return t
        t = -b + root
        if t > 0.001:
            return t
        return -1.0


def render(width, height, spheres, light):
    red = 0.0
    green = 0.0
    blue = 0.0
    y = 0
    while y < height:
        x = 0
        while x < width:
            sx = (x - width * 0.5) / height
            sy = (y - height * 0.5) / height
            direction = Vector(sx, -sy, 1.0).unit()
            origin = Vector(0.0, 0.0, -4.0)
            best = 1.0e30
            nearest = None
            i = 0
            while i < len(spheres):
                t = spheres[i].hit(origin, direction)
                if t > 0.0 and t < best:
                    best = t
                    nearest = spheres[i]
                i += 1
            if nearest is not None:
                point = origin.plus(direction.times(best))
                normal = point.minus(nearest.centre).unit()
                to_light = light.minus(point).unit()
                lambert = normal.dot(to_light)
                if lambert < 0.0:
                    lambert = 0.0
                view = Vector(0.0, 0.0, -1.0)
                reflect = normal.times(2.0 * normal.dot(to_light)).minus(to_light)
                spec = reflect.dot(view)
                if spec < 0.0:
                    spec = 0.0
                spec = spec * spec * spec * spec
                shade = 0.08 + 0.9 * lambert
                red += nearest.colour[0] * shade + spec * 0.9
                green += nearest.colour[1] * shade + spec * 0.9
                blue += nearest.colour[2] * shade + spec * 0.9
            x += 1
        y += 1
    return red, green, blue


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    spheres = [
        Sphere(Vector(-1.0, 0.0, 0.0), 0.6, (0.9, 0.2, 0.2)),
        Sphere(Vector(0.8, -0.1, 0.3), 0.5, (0.2, 0.8, 0.3)),
        Sphere(Vector(0.1, 0.7, -1.2), 0.4, (0.2, 0.3, 0.9)),
    ]
    light = Vector(4.0, 5.0, -3.0)
    r, g, b = render(size, size, spheres, light)
    print("%.9f %.9f %.9f" % (r, g, b))


main()
