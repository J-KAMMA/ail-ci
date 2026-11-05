"""advparse: a tiny text-adventure command parser and world (stdin commands)."""
import sys

class Room:
    def __init__(self, name, desc, exits):
        self.name, self.desc, self.exits = name, desc, exits

class Item:
    def __init__(self, name, desc, where, points, container, opened):
        self.name, self.desc, self.where, self.points = name, desc, where, points
        self.container, self.opened, self.contents = container, opened, []

class Player:
    def __init__(self, room):
        self.room, self.inventory, self.last_item = room, [], ""
        self.moves, self.score, self.visited = 0, 0, [room]
        self.door_open = False


ROOMS = {
    "hall": Room("hall", "a wide hall with a cold stone floor",
                 {"north": "kitchen", "east": "garden", "up": "library",
                  "down": "cellar", "west": "vault"}),
    "kitchen": Room("kitchen", "a warm kitchen smelling of apples", {"south": "hall"}),
    "garden": Room("garden", "a walled garden with damp grass", {"west": "hall"}),
    "cellar": Room("cellar", "a damp cellar lit by one small window", {"up": "hall"}),
    "library": Room("library", "a dusty library of tall shelves", {"down": "hall"}),
    "vault": Room("vault", "a small vault with a stone floor", {"east": "hall"}),
}
ITEM_SPECS = (
    ("brass key", "a small brass key", "cabinet", 5, False, False),
    ("iron key", "a heavy iron key", "garden", 0, False, False),
    ("lamp", "a brass oil lamp", "cellar", 5, False, False),
    ("coin", "a gold coin", "chest", 10, False, False),
    ("apple", "a red apple", "kitchen", 0, False, False),
    ("book", "a book of maps", "library", 5, False, False),
    ("rope", "a coil of rope", "garden", 0, False, False),
    ("sword", "a rusty sword", "cellar", 0, False, False),
    ("chest", "a wooden chest", "kitchen", 0, True, False),
    ("cabinet", "a tall cabinet", "library", 0, True, False),
)
ITEMS = {s[0]: Item(s[0], s[1], s[2], s[3], s[4], s[5]) for s in ITEM_SPECS}
ITEM_NAMES = ("apple", "book", "brass key", "coin", "iron key", "lamp", "rope", "sword")
CONTAINER_NAMES = ("cabinet", "chest")
for s in ITEM_SPECS:
    if s[2] in CONTAINER_NAMES: ITEMS[s[2]].contents.append(s[0])
DIRECTIONS = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up",
              "d": "down", "north": "north", "south": "south", "east": "east",
              "west": "west", "up": "up", "down": "down"}
ARTICLES = ("a", "an", "the")

def choices(names):
    parts = ["the " + n for n in names]
    if len(parts) == 2: return parts[0] + " or " + parts[1]
    if len(parts) > 2:
        return ", ".join(parts[:-1]) + " or " + parts[-1]
    return parts[0]

def visible_names(p):
    return [n for n in ITEM_NAMES + CONTAINER_NAMES if ITEMS[n].where == p.room]

def resolve(p, words, candidates):
    phrase = " ".join(words)
    if phrase == "it":
        return (p.last_item, 0) if p.last_item else ("", 1)
    matches = []
    for name in candidates:
        parts = name.split(" ")
        if len(parts) >= len(words) and parts[len(parts) - len(words):] == words:
            if name not in matches:
                matches.append(name)
    if not matches: return ("", 1)
    if len(matches) > 1:
        print("which do you mean, " + choices(matches) + "?")
        return ("", 2)
    p.last_item = matches[0]
    return (matches[0], 0)

def missing(phrase):
    if phrase == "it":
        print("I don't know what \"it\" refers to.")
    else:
        print("I don't see any \"" + phrase + "\" here.")

def look(p):
    room = ROOMS[p.room]
    print("you are in the " + room.name + ".")
    print(room.desc + ".")
    names = visible_names(p)
    if names:
        print("you see " + choices(names) + ".")
    for n in CONTAINER_NAMES:
        box = ITEMS[n]
        if box.where == p.room and box.opened and box.contents:
            print("the " + n + " contains " + choices(box.contents) + ".")
    print("exits: " + ", ".join(room.exits) + "." if room.exits else "there are no obvious exits.")

def move_player(p, direction):
    way = DIRECTIONS.get(direction, "")
    room = ROOMS[p.room]
    if way == "" or way not in room.exits:
        print("you can't go that way.")
        return
    if way == "west" and p.room == "hall" and not p.door_open:
        print("the door is locked.")
        return
    p.room = room.exits[way]
    if p.room not in p.visited:
        p.visited.append(p.room)
        if p.room != "hall":
            p.score = p.score + 5
    look(p)

def take(p, words):
    candidates = [n for n in ITEM_NAMES if ITEMS[n].where == p.room or
                  (ITEMS[n].where in CONTAINER_NAMES and ITEMS[ITEMS[n].where].where == p.room)]
    candidates = candidates + [n for n in CONTAINER_NAMES if ITEMS[n].where == p.room]
    name, status = resolve(p, words, candidates)
    if status == 1:
        missing(" ".join(words))
    if status != 0: return
    item = ITEMS[name]
    if item.container:
        print("you can't take the " + name + ".")
        return
    if item.where in CONTAINER_NAMES:
        box = ITEMS[item.where]
        if not box.opened:
            print("the " + box.name + " is closed.")
            return
        box.contents.remove(name)
        item.where = ""
    item.where = ""
    p.inventory.append(name)
    if item.points > 0:
        p.score = p.score + item.points
        item.points = 0
    print("you take the " + name + ".")

def drop(p, words):
    phrase = " ".join(words)
    name, status = resolve(p, words, p.inventory)
    if status == 1:
        if phrase == "it":
            missing(phrase)
        else:
            print("you are not carrying the " + phrase + ".")
    if status != 0:
        return
    p.inventory.remove(name)
    ITEMS[name].where = p.room
    print("you drop the " + name + ".")

def find_container(p, words):
    phrase = " ".join(words)
    name, status = resolve(p, words, list(CONTAINER_NAMES))
    if status != 0:
        if status == 1:
            missing(phrase)
        return ("", status)
    if ITEMS[name].where != p.room:
        print("I don't see any \"" + phrase + "\" here.")
        return ("", 1)
    return (name, 0)

def open_container(p, words, verb):
    name, status = find_container(p, words)
    if status != 0: return
    box = ITEMS[name]
    if verb == "open":
        if box.opened:
            print("the " + name + " is already open.")
            return
        box.opened = True
        print("you open the " + name + ".")
        if box.contents:
            print("inside you see " + choices(box.contents) + ".")
    else:
        if not box.opened:
            print("the " + name + " is already closed.")
            return
        box.opened = False
        print("you close the " + name + ".")

def put(p, words):
    split_at = words.index("in") if "in" in words else -1
    if split_at < 1:
        print("what do you want to put?")
        return
    item_words = words[0:split_at]
    box_words = words[split_at + 1:]
    if not box_words:
        print("put it in what?")
        return
    name, status = resolve(p, item_words, p.inventory)
    if status == 1:
        print("you are not carrying the " + " ".join(item_words) + ".")
        return
    if status == 2:
        return
    box_name, box_status = find_container(p, box_words)
    if box_status != 0:
        return
    box = ITEMS[box_name]
    if not box.opened:
        print("the " + box_name + " is closed.")
        return
    p.inventory.remove(name)
    box.contents.append(name)
    ITEMS[name].where = box_name
    print("you put the " + name + " in the " + box_name + ".")

def examine(p, words):
    if not words:
        print("what do you want to examine?")
        return
    phrase = " ".join(words)
    if phrase == "door":
        if p.room == "hall":
            print("a heavy oak door with an iron lock.")
        else:
            print("I don't see any \"door\" here.")
        return
    names = visible_names(p) + list(p.inventory)
    name, status = resolve(p, words, names)
    if status == 1:
        missing(phrase)
    if status != 0:
        return
    item = ITEMS[name]
    print(item.desc + ".")
    if item.container:
        print("the " + name + " is open." if item.opened else "the " + name + " is closed.")
        if item.opened and item.contents:
            print("inside you see " + choices(item.contents) + ".")

def do_command(p, words):
    verb = words[0]
    rest = words[1:]
    if verb in ("go", "walk"):
        if rest:
            move_player(p, rest[0])
        else:
            print("go where?")
    elif verb in DIRECTIONS:
        move_player(p, verb)
    elif verb in ("take", "get") or (verb == "pick" and rest[:1] == ["up"]):
        if verb == "pick":
            rest = rest[1:]
        if rest:
            take(p, rest)
        else:
            print("what do you want to take?")
    elif verb == "drop":
        if rest:
            drop(p, rest)
        else:
            print("what do you want to drop?")
    elif verb == "put":
        put(p, rest)
    elif verb in ("open", "close"):
        if not rest:
            print("what do you want to " + verb + "?")
        elif rest == ["door"]:
            if verb == "open" and "brass key" not in p.inventory:
                print("the door will not move.")
                sys.exit(3)
            p.door_open = verb == "open"
            print("the door opens." if verb == "open" else "the door is closed.")
        else:
            open_container(p, rest, verb)
    elif verb in ("look", "l"):
        look(p)
    elif verb in ("examine", "x"):
        examine(p, rest)
    elif verb in ("inventory", "i"):
        print("you are carrying " + choices(p.inventory) + "." if p.inventory
              else "you are empty-handed.")
    elif verb == "score":
        print("score %d of 50 in %d moves" % (p.score, p.moves))
    elif verb == "quit":
        print("score %d of 50 in %d moves" % (p.score, p.moves))
        sys.exit(0)
    else:
        print("I don't understand \"" + verb + "\".")

def main() -> int:
    p = Player("hall")
    print("welcome to advparse.")
    look(p)
    for raw in sys.stdin.read().splitlines():
        print("> " + raw)
        words = [w for w in raw.lower().split() if w not in ARTICLES]
        if words:
            p.moves = p.moves + 1
            do_command(p, words)
    print("score %d of 50 in %d moves" % (p.score, p.moves))
    return 0


if __name__ == "__main__":
    sys.exit(main())
