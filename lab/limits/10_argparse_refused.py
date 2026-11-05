import argparse

parser = argparse.ArgumentParser(description="demo")
parser.add_argument("name")
print(parser.parse_args().name)
